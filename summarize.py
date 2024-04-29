import os
import sys
import glob 
import textwrap
from openai import OpenAI

def do_summary(transcript, client, prompt_file):
    with open(prompt_file, 'r') as file:
        prompt = file.read()

    completion = client.chat.completions.create(model="gpt-4-0125-preview", 
        messages=[
        {"role": "system", "content" : "You are a chatbot which can summarize long transcripts."},
        {"role": "user", "content" : f'{prompt}{transcript}'},
        ])
    
    return completion.choices[0].message.content

def summarize(input_dir, prompt_files, openai_api_key):

    if input_dir is None:
        print("Please provide an input directory.")
        return
    
    print()
    print("--------------------")
    print("SUMMARIZE")
    print("--------------------")
    print()

    transcript_path = os.path.join(input_dir, 'transcript.txt')
    if not os.path.exists(transcript_path):
        print("transcript.txt not found in the input directory.")
        sys.exit(1)

    with open(transcript_path, 'r') as file:
        transcript = file.read()

    if not prompt_files:
        print("  No prompts to use to summarize.")
        return

    client = OpenAI(api_key=openai_api_key)

    for prompt_file in prompt_files:
        # Call your command here
        print()
        print(f"  - Prompt {prompt_file}...")
        
        summary = do_summary(transcript, client, prompt_file)

        filename = os.path.splitext(os.path.basename(prompt_file))[0].replace("prompt_", "")
        filename = f"summary_{filename}.txt"
        output_path = os.path.join(input_dir, filename)
        with open(output_path, 'w') as file:
            file.write(summary)
        print()
        print("    Result:")
        print("    ---------")
        terminal_width = os.get_terminal_size().columns
        # Split the summary into lines, then indent and wrap each line
        summary_lines = summary.split('\n')
        wrapped_summary = '\n'.join('\n'.join(textwrap.wrap(line, width=terminal_width, initial_indent='     ', subsequent_indent='     ')) for line in summary_lines)
        print(wrapped_summary)
        print("    ---------")
        print(f"    Written to {output_path}.")
        print()
        print()


