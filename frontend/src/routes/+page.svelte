<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import axios from 'axios';

  let files: FileList | null = null;
  let goal = 'general_transcription';
  let status = 'idle';
  let progress = 0;
  let message = '';
  let intervalId: number;
  let dragover = false;
  let processedFiles: string[] = [];
  let fileInputRef: HTMLInputElement;

  const goals = [
    'general_transcription',
    'meeting_minutes',
    'podcast_summary',
    'lecture_notes',
    'interview_highlights'
  ];

  async function handleSubmit() {
    if (!files || files.length === 0) return;

    const formData = new FormData();
    formData.append('file', files[0]);
    formData.append('goal', goal);

    try {
      status = 'uploading';
      message = 'Uploading file...';
      progress = 0;

      const response = await axios.post('http://localhost:8000/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          progress = percentCompleted;
        }
      });

      console.log('Upload response:', response.data);
      status = 'processing';
      message = 'File uploaded. Starting processing...';
      progress = 0;
      startStatusCheck();
    } catch (error) {
      console.error('Error uploading file:', error);
      status = 'error';
      message = 'Error uploading file';
    }
  }

  function startStatusCheck() {
    checkStatus();
    intervalId = setInterval(checkStatus, 2000);  // Check every 2 seconds
  }

  async function checkStatus() {
    try {
      const response = await axios.get('http://localhost:8000/status');
      console.log('Full status response:', response);
      if (response.data) {
        status = response.data.status;
        progress = response.data.progress;
        message = response.data.message;
        console.log(`Status: ${status}, Progress: ${progress}, Message: ${message}`);

        if (status === 'completed') {
          clearInterval(intervalId);
          downloadProcessedFiles();
        } else if (status === 'error') {
          clearInterval(intervalId);
        }
      }
    } catch (error) {
      console.error('Error checking status:', error);
      status = 'error';
      message = 'Error checking status';
      clearInterval(intervalId);
    }
  }

  async function downloadProcessedFiles() {
    try {
      console.log('Requesting download...');
      const response = await axios.get('http://localhost:8000/download', {
        responseType: 'blob'
      });
      console.log('Download response received:', response);
      const blob = new Blob([response.data], { type: 'application/zip' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'processed_files.zip');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      console.log('Download initiated');
    } catch (error) {
      console.error('Error downloading processed files:', error);
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    dragover = true;
  }

  function handleDragLeave() {
    dragover = false;
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    dragover = false;
    files = e.dataTransfer?.files || null;
  }

  function handleClick() {
    fileInputRef.click();
  }

  onDestroy(() => {
    if (intervalId) clearInterval(intervalId);
  });
</script>

<main class="container">
  <div class="header">
    <img src="/illustration.png" alt="AI Video Summarizer Illustration" class="illustration" />
    <h1>SamurAI - Video Summarizer</h1>
    <p>Transcribe, summarize, and create smart clips from video and audio content.</p>
  </div>

  <form on:submit|preventDefault={handleSubmit}>
    <div 
      class="drop-area"
      class:dragover 
      on:dragover={handleDragOver} 
      on:dragleave={handleDragLeave} 
      on:drop={handleDrop}
      on:click={handleClick}
    >
      <div class="drop-area-content">
        {#if files && files.length > 0}
          <p class="file-name">{files[0].name}</p>
        {:else}
          <svg xmlns="http://www.w3.org/2000/svg" width="50" height="50" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="17 8 12 3 7 8"></polyline>
            <line x1="12" y1="3" x2="12" y2="15"></line>
          </svg>
          <p>Drag and drop a video file here, or click to select</p>
        {/if}
      </div>
      <input 
        bind:this={fileInputRef}
        type="file" 
        id="file" 
        accept="video/*" 
        on:change={(e) => files = e.target.files} 
        hidden
      >
    </div>

    <label for="goal">
      Select a summary type:
      <select id="goal" bind:value={goal}>
        {#each goals as goalOption}
          <option value={goalOption}>{goalOption.replace('_', ' ')}</option>
        {/each}
      </select>
    </label>

    <button type="submit" disabled={!files || files.length === 0 || status !== 'idle'}>Upload and Process</button>
  </form>

  {#if status !== 'idle'}
    <article class="status-container">
      <header>Processing Status</header>
      <p>Status: {status}</p>
      <p>Progress: {progress}%</p>
      <p>Message: {message}</p>
      <progress value={progress} max="100"></progress>
    </article>
  {/if}

  {#if status === 'completed'}
    <article>
      <header>Download Processed Files</header>
      <button on:click={downloadProcessedFiles}>Download Zip</button>
    </article>
  {/if}
</main>

<style>
 .header {
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 2rem;
    flex-direction: column;
  }

  .illustration {
    width: 250px;
    height: 250px;
    margin-right: 1rem;
  }

  @media (max-width: 600px) {
    .header {
      flex-direction: column;
    }

    .illustration {
      margin-right: 0;
      margin-bottom: 1rem;
    }
  }

  h1 {
    font-size: 2rem;
    margin-bottom: 0;
    margin-top: 0;
    color: var(--color);
  }

  .drop-area {
    border: 2px dashed var(--primary);
    border-radius: var(--border-radius);
    padding: 2rem;
    text-align: center;
    cursor: pointer;
    margin-bottom: 1rem;
    transition: all 0.3s ease;
  }

  .drop-area-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 150px;
  }

  .drop-area svg {
    margin-bottom: 1rem;
  }

  .drop-area.dragover {
    background-color: var(--primary-hover);
    border-color: var(--primary-focus);
  }

  .drop-area .file-name {
    font-weight: bold;
    word-break: break-all;
  }

  .status-container {
    margin-top: 2rem;
  }
</style>
