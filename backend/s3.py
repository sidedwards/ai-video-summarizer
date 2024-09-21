import os
import subprocess

from log import logger


def upload_to_s3(file_path, config):
    logger.debug(f"Uploading file to S3: {file_path}")
    command = f"{config['aws_cli_path']} s3 cp {file_path} s3://{config['s3_bucket']}/public/{os.path.basename(file_path)}"
    logger.debug(f"S3 upload command: {command}")
    subprocess.run(command, shell=True, check=True)
    logger.info(f"File uploaded successfully to S3: {file_path}")


def get_s3_presigned_url(file_name, config):
    logger.debug(f"Getting presigned URL for file: {file_name}")
    command = f"{config['aws_cli_path']} s3 presign s3://{config['s3_bucket']}/public/{file_name}"
    logger.debug(f"S3 presign command: {command}")
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, check=True
    )
    presigned_url = result.stdout.strip()
    logger.info(f"Presigned URL generated: {presigned_url}")
    return presigned_url
