import os
import re

def extract_speaker_name(file, extension):
    file_name = os.path.basename(file)  # strip off the path
    regex = r"^\d*[-_]?(.+?)(?:_0)?(?:\.[a-zA-Z0-9]{2,4})?\." + re.escape(extension) + "$"
    match = re.match(regex, file_name)
    if match:
        return match.group(1)
    else:
        raise ValueError(f"Could not parse speaker name from filename '{file_name}'")