import sys
import json
import os
import re
import glob
import readline
from typing import Dict, Optional
import torch
import whisper_timestamped as whisper
from configuration import get_configuration
from recognize import recognize
from assemble import assemble
from summarize import summarize
from utils import extract_speaker_name

def json_string_or_path(json_string_or_path):
    if not json_string_or_path:
        return None

    deserialized_object = None
    try:
        deserialized_object = json.loads(json_string_or_path)
    except json.JSONDecodeError:
        # If it's not a valid JSON string, treat it as a file path
        if os.path.exists(json_string_or_path):
            with open(json_string_or_path, 'r') as f:
                deserialized_object = json.load(f)

    return deserialized_object

def load_names(names_setting, input_dir):
    names = json_string_or_path(names_setting)
    if names is None:
        # Look for names.json in input_dir
        names_file_path = os.path.join(input_dir, 'names.json')
        if not os.path.exists(names_file_path):
            # If not found, look one folder up
            names_file_path = os.path.join(input_dir, '..', 'names.json')
        if os.path.exists(names_file_path):
            # If found, prompt the user whether to use it
            use_names_file = input(f"  Found a names file at {names_file_path}. Do you want to use it? (y/n): ")
            if use_names_file.lower() == 'y':
                with open(names_file_path, 'r') as f:
                    names = json.load(f)
                    print(f"    Loaded {len(names)} speaker name{'s' if len(names) > 1 else ''} from {names_file_path}.")
    else:
        print(f" Loaded {len(names)} speaker name{'s' if len(names) > 1 else ''}.")

    return names

def load_corrections(corrections_setting, input_dir):
    corrections = None
    correction_setting_dic = json_string_or_path(corrections_setting)
    if correction_setting_dic is None:
        # Look for corrections.json in input_dir
        corrections_file_path = os.path.join(input_dir, 'corrections.json')
        if not os.path.exists(corrections_file_path):
            # If not found, look one folder up
            corrections_file_path = os.path.join(input_dir, '..', 'corrections.json')
        if os.path.exists(corrections_file_path):
            # If found, prompt the user whether to use it
            use_corrections_file = input(f"  Found a corrections file at {corrections_file_path}. Do you want to use it? (y/n): ")
            if use_corrections_file.lower() == 'y':
                with open(corrections_file_path, 'r') as f:
                    correction_setting_dic = json.load(f)
                    print(f"    Loaded corrections from {corrections_file_path}.")
    if correction_setting_dic is not None:
        # this was defined as "correct string": ["incorrect string", "incorrect string", ...] because that's 
        # easier to write out multiple corrections to the same value, but now we need to flip it so that we 
        # can actually use the dictionary to look up words and see if they need correcting
        corrections = {incorrect: correct for correct, incorrects in correction_setting_dic.items() for incorrect in incorrects}
        print(f" Loaded {len(corrections)} correction{'s' if len(corrections) > 1 else ''}.")
        print()

    return corrections

def check_names(names: Optional[Dict[str, str]], files, extension):
    if names is None:
        names = {}
    for file in files:
        speaker_name = extract_speaker_name(file, extension)
        if speaker_name not in names:
            print()
            readline.set_startup_hook(lambda: readline.insert_text(speaker_name))
            try:
                value = input(f" Enter the proper speaker name for '{speaker_name}' (press enter to accept, or backspace it all and enter nothing to skip this file): ")
            finally:
                readline.set_startup_hook()  # remove hook again
            names[speaker_name] = value if value else None
    return names

def load_prompt_files(input_dir, prompt_type):
    prompt_files = []
    directories = [input_dir, os.path.dirname(input_dir), os.path.dirname(os.path.realpath(__file__))]

    for directory in directories:
        files = glob.glob(os.path.join(directory, f'prompt_{prompt_type}_*.txt'))
        if files:
            print()
            print(f"  Found the following prompt files in {directory}:")
            print()
            for file in files:
                print(f"  - {file}")
            print()
            use_files = input("  Use these files? (y/n): ")
            if use_files.lower() == 'y':
                prompt_files.extend(files)
                break
            print()

    if not prompt_files:
        print("  No prompt files found.")

    return prompt_files
def check_cuda():
    if not torch.cuda.is_available():
        print("\033[93m WARNING: CUDA (gpu support) is not available!\n"
              "\n If you are in Docker, you may have forgotten to specify `--gpus all`."
              "\n Otherwise, this is a bit more of a rabbit hole than can be delved here "
              "\n (it depends on your operating system and environment, but it's quite "
              "\n googleable).\n"
              "\n You can try to continue without it, but:"
              "\n  - RECOGNIZE may be excruciatingly slow, or just not work at all."
              "\n  - ASSEMBLE may fail when trying to auto-repunctuate out of sync items.\n"
              "\n (SUMMARIZE workloads should be unaffected.)\n \033[0m")
        response = input("Do you want to continue running? (y/n): ")
        if response.lower() not in ["y", "yes"]:
            exit()
    else:
        print("  CUDA is available.")

def main():
    # sys.argv contains the command-line arguments
    # sys.argv[0] is the script name
    # sys.argv[1:] are the arguments passed to the script
    args = sys.argv[1:]
    config = get_configuration(args)
    inputDir = config['inputDir']
    no_ellipses = config.get('noEllipses', False)
    disfluent_comma = config.get('disfluentComma', False)
    no_asterisks = config.get('noAsterisks', False)
    show_timestamps = config.get('showTimestamps', False)

    print()
    print("--------------------")
    print("PRE-CHECK")
    print("--------------------")
    print()

    check_cuda()
    corrections = load_corrections(config.get('corrections'), inputDir)

    operation = config['operationMode']
    if operation in ['recognize', 'semiauto', 'fullauto']:
        check_names_extension = config.get('extension', 'ogg').strip() or 'ogg'
    else:
        check_names_extension = 'words.json'

    files = glob.glob(os.path.join(inputDir, f"*.{check_names_extension}"))

    if not files:
        print()
        print(f" No {check_names_extension} files were found at {inputDir}.")
        print()
        sys.exit()

    print(f" Found {len(files)} files to work on at {inputDir}:")
    print()
    for file in files:
        filename = os.path.basename(file)
        print(f'  - {filename}')
    print()
    names = check_names(load_names(config.get('names'), inputDir), files, check_names_extension)

    openai_api_key = config.get('openApiKey')
    prompt_type = config.get('promptType')
    prompt_files = []
    if operation in ['summarize', 'fullauto']:
        if (prompt_type is None) or (prompt_type == ''):
            print("  Prompt Type is required for summarize (or fullauto) operation mode.")
            sys.exit()
        prompt_files = load_prompt_files(inputDir, prompt_type)
        if not prompt_files:
            print("  At least one prompt file must be found for summarize (or fullauto) operation mode.")
            sys.exit()
        if (openai_api_key is None) or (openai_api_key == ''):
            print("  OpenAI API key is required for summarize (or fullauto) operation mode.")
            sys.exit()

    operation_modes = {
        'recognize': lambda: recognize(inputDir, names, config['fast']),
        'assemble': lambda: assemble(inputDir, corrections, names, no_ellipses, disfluent_comma, no_asterisks, show_timestamps),
        'summarize': lambda: summarize(inputDir, prompt_files, openai_api_key),
        'semiauto': lambda: [recognize(inputDir, names, config['fast']), assemble(inputDir, corrections, names, no_ellipses, disfluent_comma, no_asterisks, show_timestamps)],
        'fullauto': lambda: [recognize(inputDir, names, config['fast']), assemble(inputDir, corrections, names, no_ellipses, disfluent_comma, no_asterisks, show_timestamps), summarize(inputDir, prompt_files, openai_api_key)]
    }

    print("--------------------")

    if operation in operation_modes:
        operation_modes[operation]()
    else:
        print(f"Invalid operation: {operation}")    

if __name__ == '__main__':
    main(sys.argv[1:])