# you'll need to have already done: 
#  docker build https://github.com/linto-ai/whisper-timestamped.git -t whisper_timestamped
FROM whisper_timestamped 

# install packages it doesn't include
RUN pip install --no-cache-dir deepmultilingualpunctuation openai

WORKDIR /usr/src/tasmas

COPY . /usr/src/tasmas

RUN cd /usr/src/tasmas/ && pip3 install .