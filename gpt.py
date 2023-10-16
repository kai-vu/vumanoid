import logging
import openai
import os

from state import State

log = logging.getLogger(__name__)

class GPT:
    def __init__(self, state_obj: State, persona: str, api_key:str):
        self.state = state_obj
        self.persona = persona
        if api_key:
            with open('SECRETKEY', 'w') as fw:
                print(api_key, file=fw)
        elif os.path.exists('SECRETKEY'):
            api_key = open('SECRETKEY').read().strip()
        log.info(f'Using OpenAI API key {api_key}')
        openai.api_key = api_key
        
    
    def respond(self, keyword, content):
        old_messages = [
            # outputs (>) are assistant messages, inputs (<) are user messages
            {"role": ("assistant" if m[0] == '>' else "user"), "content": m[1:]}
            for m in self.state.read().splitlines()
        ]
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=(
                [{"role": "system", "content": self.persona}]
                + old_messages
                + [{"role": "user", "content": f"{keyword} {content}"}]
            )
        )
        reply = completion.choices[0].message.content.replace('\n','')
        log.info(f'Got reply {reply}')
        if ' ' in reply:
            reply_keyword, reply_content = reply.split(' ', 1)
        else:
            reply_keyword, reply_content = reply, ''
        return self.state.output(reply_keyword, reply_content)
