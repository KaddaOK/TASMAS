from setuptools import setup, find_packages

setup(name='tasmas', 
      version='0.1',    
      author='Kadda OK',
      description='TASMAS (Transcribe And Summarize Multiple Audio Stems) transcribes and interleaves per-speaker audio recordings into a single threaded transcript, which it can optionally then summarize.',
      py_modules=['tasmas', 'assemble', 'configuration', 'recognize', 'summarize', 'utils'],
      install_requires=[
        'whisper_timestamped',
        'auditok',
        'deepmultilingualpunctuation',
        'openai'
      ],
      entry_points={
        'console_scripts': [
          'tasmas=tasmas:main'
        ],
    })