import logging
from logging.handlers import RotatingFileHandler
import os
import json


# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[
                        RotatingFileHandler('debug.log', maxBytes=10000000, backupCount=5),
                        logging.StreamHandler()
                    ])
logging.getLogger('multipart').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def save_debug_info(output_folder, content, topics, clips):
    debug_file = os.path.join(output_folder, "debug_info.txt")
    with open(debug_file, "w") as f:
        f.write("Generated Content:\n")
        f.write(content)
        f.write("\n\nExtracted Topics:\n")
        json.dump(topics, f, indent=2)
        f.write("\n\nGenerated Clips:\n")
        json.dump(clips, f, indent=2)
    logger.info(f"Debug information saved to {debug_file}")
