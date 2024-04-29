import json
import os
import glob
import re
import math
import uuid
import warnings
from operator import attrgetter
from typing import List, Dict, Optional
from deepmultilingualpunctuation import PunctuationModel
from tqdm import tqdm
from utils import extract_speaker_name

class WtWordEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (WtWord, WtWordList)):
            return o.to_dict()
        return super().default(o)
    
class WtWordList:
    def __init__(self, words):
        if len(set(word.speaker for word in words)) > 1:
            raise ValueError("All words in a WtWordList must have the same speaker")
        self.words = words

    @property
    def speaker(self):
        return self.words[0].speaker if self.words else None

    @property
    def start(self):
        return min(word.start for word in self.words)

    @property
    def end(self):
        return max(word.end for word in self.words)

    @property
    def text(self):
        return " ".join(word.text for word in self.words)

    def to_dict(self):
        return {
            'speaker': self.speaker,
            'start': self.start,
            'end': self.end,
            'text': self.text,
            'words': [word.to_dict() for word in self.words]
        }
    
class WtWord:
    def __init__(self, speaker, text, start, end):
        self.id = uuid.uuid4()
        self.speaker = speaker
        self.text = text
        self.start = start
        self.end = end
    def to_dict(self):
        return {
            'id': str(self.id),
            'speaker': self.speaker,
            'text': self.text,
            'start': self.start,
            'end': self.end
        }

def assemble(input_dir, corrections, names, no_ellipses, disfluent_comma, no_asterisks, show_timestamps):
    if input_dir is None:
        print("Please provide an input directory.")
        return
    
    print()
    print("--------------------")
    print("ASSEMBLE")
    print("--------------------")
    print()

    ext = "words.json"
    files = glob.glob(os.path.join(input_dir, '*.' + ext))

    if not files:
        print()
        print(f" ERROR: No .{ext} files were found at {input_dir}.")
        print()
        return

    print(f" Found {len(files)} .{ext} files at {input_dir}.")
    print()

    all_chunks = extract_all_chunks(names, no_ellipses, disfluent_comma, no_asterisks, files)

    # Sort all chunks by start timestamp
    print(" Sorting...")
    sorted_chunks = sorted(all_chunks, key=attrgetter('start', 'speaker', 'end'))
    print(" Normalizing...")
    normalized_items = normalize_items(sorted_chunks)
    """normaljson = os.path.join(input_dir, 'normalized.json')
    with open(normaljson, 'w') as f:
        f.write(json.dumps(normalized_items, cls=WtWordEncoder, indent=2))"""
    print(" Collapsing...")
    collapsed_items = collapse_adjacent(normalized_items)
    """collapsejson = os.path.join(input_dir, 'collapsed.json')
    with open(collapsejson, 'w') as f:
        f.write(json.dumps(collapsed_items, cls=WtWordEncoder, indent=2))"""
    print(" Formatting...")
    # max timestamp value for formatting 
    max_timestamp =  max(value for chunk in sorted_chunks for value in [chunk.start, chunk.end])
    timestamp_digits = int(math.ceil(math.log10(max_timestamp)))
    format_string = "{:0{}.2f}".format(max_timestamp, timestamp_digits)

    # Find the maximum width of the speaker name
    max_speaker_width = max(len(chunk.speaker) for chunk in sorted_chunks)
    print(" Checking for problems...")
    out_of_sync_items = get_out_of_sync_items(input_dir, format_string, max_speaker_width, collapsed_items)  
    if len(out_of_sync_items) > 0:
        #run them through the punctuation model and collapse again
        print(f"  Found {len(out_of_sync_items)} out-of-sync items. Attempting to auto-punctuate and re-collapse...")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            punctuationModel = PunctuationModel()
            changesMade = 0
            for item, _ in out_of_sync_items:
                repunctuated = punctuationModel.restore_punctuation(item.text)
                if len(repunctuated) > len(item.text):
                    update_word_texts(item, repunctuated, all_chunks)
                    changesMade += 1
            if changesMade > 0:
                print(f"  Made changes to punctuation on {changesMade} lines.")
                print("  Re-sorting...")
                sorted_chunks = sorted(all_chunks, key=attrgetter('start', 'speaker', 'end'))
                print("  Re-normalizing...")
                normalized_items = normalize_items(sorted_chunks)
                print("  Re-collapsing...")
                collapsed_items = collapse_adjacent(normalized_items)
                print("  Checking for problems again...")
                out_of_sync_items = get_out_of_sync_items(input_dir, format_string, max_speaker_width, collapsed_items)  
                if len(out_of_sync_items) > 0:     
                    write_out_of_sync_items(input_dir, max_speaker_width, out_of_sync_items)

    # option repunctuate everything
    """print(" Repunctuating all items...")                    
    punctuationModel = PunctuationModel()
    for item in tqdm(collapsed_items):
        repunctuated = punctuationModel.restore_punctuation(item.text)
        update_word_texts(item, repunctuated, item.words)"""
    print(" Writing Output...")
    output_items(input_dir, corrections, show_timestamps, format_string, max_speaker_width, collapsed_items)
    print("--------------------")

def extract_all_chunks(names: Optional[Dict[str, str]], no_ellipses: bool, disfluent_comma: bool, no_asterisks: bool, file_names: List[str]) -> List[WtWord]:
    all_chunks = []

    for file_name in file_names:
        print(f" - {os.path.basename(file_name)}")
        original_speaker = extract_speaker_name(file_name, 'words.json')
        if names and original_speaker in names and (names[original_speaker] is None or names[original_speaker] == ''):
            print(f"    Skipping because '{original_speaker}' is specified as blank.")
            print()
            continue

        speaker = names[original_speaker] if names and original_speaker in names else original_speaker
        print(f"    Extracting chunks for {speaker} ({original_speaker})...")
        extracted_chunks = extract_chunks_from_file(file_name, speaker)
        if disfluent_comma:
            insert_commas_at_disfluencies(extracted_chunks, no_asterisks)
        undisfluent_chunks = [c for c in extracted_chunks if c.text.strip() != "[*]"]
        if not no_ellipses:
            insert_ellipses_at_likely_breaks(undisfluent_chunks, no_asterisks)
        all_chunks.extend(undisfluent_chunks)
        print()

    return all_chunks

def normalize_items(sorted_chunks: List[WtWord]) -> List[WtWordList]:
    normalized_items = []
    current_sentences = {}

    for chunk in sorted_chunks:
        if chunk.text == "[*]":
            # this is just a scrubbed disfluency, skip it
            continue

        if chunk.speaker not in current_sentences or current_sentences[chunk.speaker] is None:
            current_sentences[chunk.speaker] = WtWordList([chunk])
        else:
            current_sentences[chunk.speaker].words.append(chunk)

        last_character = chunk.text.strip()[-1]
        if last_character in ['.', '!', '?', '-', ',', '~']:
            normalized_items.append(current_sentences[chunk.speaker])
            current_sentences[chunk.speaker] = None

    # catch any leftovers
    leftovers = [v for k, v in current_sentences.items() if v is not None]
    leftovers.sort(key=lambda x: x.start)
    normalized_items.extend(leftovers)

    return normalized_items

def collapse_adjacent(normalized_items: List[WtWordList]) -> List[WtWordList]:
    current_chunk = None

    collapsed_items = []

    for nextchunk in normalized_items:
        if current_chunk is None:
            current_chunk = nextchunk
            continue
        elif nextchunk.speaker != current_chunk.speaker:
            collapsed_items.append(current_chunk)
            current_chunk = nextchunk
        else:
            current_chunk.words.extend(nextchunk.words)

    # Output the last chunk
    if current_chunk is not None:
        collapsed_items.append(current_chunk)

    return collapsed_items

def get_out_of_sync_items(input_dir, format_string, max_speaker_width, collapsed_items):
    now_running_time = 0
    out_of_sync_items = []

    for item in collapsed_items:
        if item.start < now_running_time - 5:
            out_of_sync_items.append((item, round(now_running_time - item.start, 2)))
        now_running_time = item.start

    return out_of_sync_items

def write_out_of_sync_items(input_dir, max_speaker_width, potentially_needing_punctuation):
    print()
    print(f"  NOTE: There are {len(potentially_needing_punctuation)} lines with significantly earlier start timestamps than the previous line, as shown.")
    print("  Manually adding a punctuation mark to the end of one of the words of these lines in the .words.json would allow them to split at that spot, that part of them appearing before the previous speaker's line:")
    print()
    potential_punctuation_string = ""
    max_item_offset_length = max(len(str(x[1])) for x in potentially_needing_punctuation)
    max_start_length = max(len(str(x[0].start)) for x in potentially_needing_punctuation)
    max_end_length = max(len(str(x[0].end)) for x in potentially_needing_punctuation)


    for item in potentially_needing_punctuation:
        item_string = f"   [{f'{item[0].start:.2f}'.rjust(max_start_length)}-{f'{item[0].end:.2f}'.rjust(max_end_length)}] {f'-{item[1]:.2f}s'.rjust(max_item_offset_length +2)}  {item[0].speaker.rjust(max_speaker_width)}: {item[0].text}"
        print(item_string)
        potential_punctuation_string += item_string + "\n"

    punctuation_review_path = os.path.join(input_dir, "outOfSyncItems.txt")
    with open(punctuation_review_path, 'w') as file:
        file.write(potential_punctuation_string)
    print()
    print(f"  This list has been saved to {punctuation_review_path} for review.")
    print()

def update_word_texts(word_list: WtWordList, new_text: str, original_words: List[WtWord]):
    new_words = new_text.split()

    if len(new_words) != len(word_list.words):
        raise ValueError(f"The new text does not have the same number of words as the original. New count: {len(new_words)}, Old count: {len(word_list.words)}, text: '{new_text}' Original text: '{word_list.text}'")

    for wt_word, new_word in zip(word_list.words, new_words):
        if wt_word.text != new_word:
            for original_word in original_words:
                if original_word.id == wt_word.id:
                    original_word.text = new_word
                    break

def output_items(input_dir, corrections, show_timestamps, format_string, max_speaker_width, collapsed_items):
    output_builder = []

    for item in collapsed_items:
        timestamp = f"[{item.start}-{item.end}] " if show_timestamps else ""
        out_string = f"{timestamp}{item.speaker.rjust(max_speaker_width)}: \"{item.text}\""

        if corrections is not None:
            for key, value in corrections.items():
                out_string = out_string.replace(key, value)

        output_builder.append(out_string)

    output_path = os.path.join(input_dir, "transcript.txt")
    with open(output_path, 'w') as file:
        file.write('\n'.join(output_builder))
    print(f"  {len(output_builder)} lines saved as {output_path}")

def ends_with_break(chunk_text):
    last_character = chunk_text.strip()[-1]
    return last_character in ['.', '!', '?', '-', ',', '~']

def extract_chunks_from_file(file_path: str, speaker: str) -> List[WtWord]:
    chunks = []

    try:
        with open(file_path, 'r') as file:
            json_content = file.read()
        jsonData = json.loads(json_content)

        for chunkData in jsonData['segments']:
            segment_chunks = []
            for word in chunkData['words']:
                chunk = WtWord(
                    speaker = speaker,
                    text = word['text'].strip() if word['text'] else "",
                    start = word['start'],
                    end = word['end']
                )
                segment_chunks.append(chunk)

            chunks.extend(segment_chunks)
    except Exception as ex:
        print(f"Error processing file {file_path}: {str(ex)}")

    return chunks

def insert_commas_at_disfluencies(segment_chunks: List[WtWord], no_asterisks: bool):
    if len(segment_chunks) > 1:
        for i in range(1, len(segment_chunks)):
            current_word = segment_chunks[i]
            prvs_word = segment_chunks[i - 1]
            if current_word.speaker != prvs_word.speaker:
                raise ValueError("Only meant to be used on single-speaker collection")
            if current_word.text == "[*]" and not ends_with_break(prvs_word.text):
                prvs_word.text = prvs_word.text.strip() + ("" if no_asterisks else "*") + ","

def insert_ellipses_at_likely_breaks(segment_chunks: List[WtWord], no_asterisks: bool):
    if len(segment_chunks) > 1:
        for i in range(1, len(segment_chunks)):
            current_word = segment_chunks[i]
            prvs_word = segment_chunks[i - 1]
            if current_word.speaker != prvs_word.speaker:
                raise ValueError("Only meant to be used on single-speaker collection")
            if current_word.start - prvs_word.end > 10 and not ends_with_break(prvs_word.text):
                prvs_word.text = prvs_word.text.strip() + ("" if no_asterisks else "*") + "..."