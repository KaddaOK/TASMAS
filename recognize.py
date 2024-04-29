import os
import json
import glob
from typing import Dict
import whisper_timestamped as whisper

from utils import extract_speaker_name

def recognize(input_dir: str, names: Dict[str, str], fast: bool = False, model_type: str = "small", device: str = "cuda", audio_ext: str = "ogg"):
    model_type = "tiny" if fast else model_type
    model = whisper.load_model(model_type, device=device)

    print()
    print("--------------------")
    print("RECOGNIZE")
    print("--------------------")
    print()
    
    files = glob.glob(os.path.join(input_dir, '*.' + audio_ext))

    if not files:
        print(f" No {audio_ext} files were found at {input_dir}.")
        print()
        return

    print(f" {len(files)} {audio_ext} files found at {input_dir}.")
    for audio_file in files:
        print(f" - {audio_file}...")
        speaker = extract_speaker_name(audio_file, audio_ext)
        if speaker in names and (names[speaker] is None or names[speaker] == ''):
            print(f"  Skipping {audio_file} because '{speaker}' is specified as blank.")
            print()
            continue
        else:
            audio = whisper.load_audio(os.path.join(input_dir, audio_file))
            if fast:
                results = whisper.transcribe(model, audio, detect_disfluencies=True, vad="auditok")
            else:
                results = whisper.transcribe(model, audio, detect_disfluencies=True, vad="auditok", beam_size=5, best_of=5, temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0))

            json_file = os.path.join(input_dir, audio_file + '.words.json')
            with open(json_file, 'w') as f:
                f.write(json.dumps(results))
            print(f"  Saved to {json_file}")
            print()
    print("--------------------")