import os
import argparse

def get_configuration(args):
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter,
                                     description='''Multi-Stem Conversational Transcriber
''')
    parser.add_argument('operationMode', type=str, 
                        choices=['recognize', 'assemble', 'summarize', 'semiauto', 'fullauto'], 
                        help='''Which step to perform:
- recognize: Transcribes all audio files found at the 
             path using whisper_timestamped and writes 
             a .words.json file for each.
- assemble:  Arranges by timecode the contents of all 
             .words.json files found at the path, 
             switching speakers at punctuation, to 
             produce a readable transcript.txt.
- summarize: Calls OpenAI API to summarize the 
             transcript.txt at the path using 
             configurable prompts.
- semiauto:  Runs recognize followed immediately by 
             assemble. (This is the recommended first 
             pass mode, as it is common to iterate on
             assemble multiple times making manual
             tweaks to the .words.json files.)
- fullauto:  Performs all steps in succession. 
 ''')
    parser.add_argument('inputDir', type=str, help='The path to the files to process.')

    recognizeConfigGroup = parser.add_argument_group('recognize mode options')
    recognizeConfigGroup.add_argument('--extension', type=str, help='''File extension of the audio files to transcribe.
Defaults to "ogg", for use with Craig recordings, but 
I would think that things like "wav" or "flac" would 
work too.
''')
    recognizeConfigGroup.add_argument('--fast', action='store_true', 
                                      help='''Prioritize recognition speed over accuracy.
Results in the following changes:
- Uses the "tiny" model instead of the "small" model 
- Uses "efficient" params rather than "accurate" ones
Honestly this really doesn't work well at all and I 
do not recommend it.
'''
)

    assembleConfigGroup = parser.add_argument_group('assemble mode options')
    assembleConfigGroup.add_argument('--noEllipses', action='store_true', help='''This script normally inserts ellipses (...) into the
transcript whenever a word is more than 5s after its
predecessor, allowing a speaker change (which is done
on punctuation). 
The --noEllipses switch suppresses this behavior.
 ''')
    assembleConfigGroup.add_argument('--disfluentComma', action='store_true', help='''Replace detected disfluencies (e.g. "um", "uh") with a
comma in the transcript. 
This may help if you are using --noEllipses.
 ''')
    assembleConfigGroup.add_argument('--noAsterisks', action='store_true', help='''When this script inserts ellipses or disfluency commas
into the transcript, it marks them with an asterisk (*)
for reference.
The --noAsterisks switch suppresses this behavior.
 ''')
    assembleConfigGroup.add_argument('--showTimestamps', action='store_true', help='''Include the start and end seconds of the phrase in 
front of each line in the transcript. 
i.e. [1905.39-1907.05]  Joe: "Look a timestamp."
 ''')
    assembleConfigGroup.add_argument('--corrections', type=str, help='''A list of known incorrect values to replace in the 
transcript output. This is a quick way to correct 
frequently misinterpreted text such as unusual names. 
Each entry is the correct word or phrase with a list of
incorrect ones. For example,
'{"Elsalor":["Elcelor", "I'll solar", "else the Lord"],
  "A'Dhem" :["Adam"] }'
This can be a path to a .json file or the actual JSON.
 ''')
    assembleConfigGroup.add_argument('--names', type=str, help='''Replacements for the speaker names as recorded in the 
filenames by discord/Craig. These should reflect the 
names used by speakers to refer to each other in the 
recordings. For example:
'{ "joey__0": "Joe",
  "randointernet3000_0": "Bob" }'
This can be a path to a .json file or the actual JSON.
You will be prompted individually for any values not
found here (and given the opportunity to skip that 
audio stem).
 ''')
    
    summarizeConfigGroup = parser.add_argument_group('summarize mode options')
    summarizeConfigGroup.add_argument('--promptType', type=str, help='''
This script will call OpenAI's GPT-4 API to summarize
the transcript as many times as it is given prompts to 
do so. It will attempt to find text files with the name
pattern "prompt_{promptType}_*.txt", in the following 
order: 
 - in the `inputDir`
 - one level above the `inputDir`
 - in the location of this script
''')
    summarizeConfigGroup.add_argument('--openApiKey', type=str, help='''Due to current LLM token limits (Q1 2024) and the very 
large number of tokens needed to summarize transcripts
of much length, the summarize operation calls ChatGPT
4 Turbo (128k tokens). As such, an OpenAI API key is 
required to run in summarize (or fullauto) mode. 
(It'll probably cost you about $0.10 USD per call.)
''')

    config = vars(parser.parse_args(args))
    
    return config