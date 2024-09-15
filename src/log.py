import logging
from logging.handlers import RotatingFileHandler
import os
import json


# Set up logging
log_file = "debug.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(log_file, maxBytes=10000000, backupCount=5),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


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
