<script lang="ts">
  import { onMount } from 'svelte';
  import axios from 'axios';

  export let config = {
    transcription_model: "replicate",
    selected_replicate_model: "whisperx",
    summarization_model: "anthropic",
    clip_generation_model: "anthropic",
    export_format: "markdown"
  };

  let loading = true;
  let error = '';

  let availableOptions: {
    transcription_models: string[];
    replicate_models: string[];
    summarization_models: string[];
    clip_generation_models: string[];
    export_formats: string[];
  } = {
    transcription_models: ["replicate"],
    replicate_models: ["whisperx", "incredibly-fast-whisper"],
    summarization_models: ["anthropic", "openai"],
    clip_generation_models: ["anthropic", "openai"],
    export_formats: ["markdown", "pdf", "docx"]
  };

  onMount(async () => {
    try {
      const response = await axios.get('http://localhost:8000/config');
      const data = response.data;
      
      // Update current config with server defaults
      config = {
        transcription_model: data.transcription_model,
        selected_replicate_model: data.selected_replicate_model,
        summarization_model: data.summarization_model,
        clip_generation_model: data.clip_generation_model,
        export_format: data.export_format
      };
      
      // Update available options
      if (data.available_options) {
        availableOptions = data.available_options;
      }
    } catch (error) {
      console.error('Error fetching config options:', error);
      error = 'Failed to load configuration options. Using defaults.';
    } finally {
      loading = false;
    }
  });
</script>

<div class="config-options">
  <details>
    <summary>Advanced Configuration</summary>
    {#if loading}
      <div class="loading">Loading configuration options...</div>
    {:else if error}
      <div class="error">{error}</div>
    {/if}
    <div class="config-grid">
      <label for="transcription_model">
        Transcription Model:
        <select id="transcription_model" bind:value={config.transcription_model}>
          {#each availableOptions.transcription_models as model}
            <option value={model}>{model}</option>
          {/each}
        </select>
      </label>

      {#if config.transcription_model === 'replicate'}
        <label for="selected_replicate_model">
          Replicate Model:
          <select id="selected_replicate_model" bind:value={config.selected_replicate_model}>
            {#each availableOptions.replicate_models as model}
              <option value={model}>{model.replace('-', ' ')}</option>
            {/each}
          </select>
        </label>
      {/if}

      <label for="summarization_model">
        Summarization Model:
        <select id="summarization_model" bind:value={config.summarization_model}>
          {#each availableOptions.summarization_models as model}
            <option value={model}>{model}</option>
          {/each}
        </select>
      </label>

      <label for="clip_generation_model">
        Clip Generation Model:
        <select id="clip_generation_model" bind:value={config.clip_generation_model}>
          {#each availableOptions.clip_generation_models as model}
            <option value={model}>{model}</option>
          {/each}
        </select>
      </label>

      <label for="export_format">
        Export Format:
        <select id="export_format" bind:value={config.export_format}>
          {#each availableOptions.export_formats as format}
            <option value={format}>{format}</option>
          {/each}
        </select>
      </label>
    </div>
  </details>
</div>

<style>
  .config-options {
    margin: 1rem 0;
  }

  .config-grid {
    display: grid;
    gap: 1rem;
    padding: 1rem;
    background: var(--card-background-color);
    border-radius: var(--border-radius);
    margin-top: 1rem;
  }

  details {
    background: var(--card-background-color);
    border-radius: var(--border-radius);
    padding: 0.5rem;
  }

  summary {
    cursor: pointer;
    padding: 0.5rem;
    font-weight: bold;
  }

  summary:hover {
    color: var(--primary);
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  select {
    width: 100%;
    padding: 0.5rem;
    border-radius: var(--border-radius);
    border: 1px solid var(--form-element-border-color);
    background: var(--form-element-background-color);
    color: var(--form-element-color);
  }

  select:focus {
    border-color: var(--primary);
    outline: none;
  }

  .loading, .error {
    padding: 1rem;
    text-align: center;
    margin: 1rem 0;
  }

  .error {
    color: var(--form-element-invalid-color);
  }

  @media (min-width: 768px) {
    .config-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }
</style> 