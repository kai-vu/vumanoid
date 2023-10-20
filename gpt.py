import logging
import openai
import os

from state import State

log = logging.getLogger(__name__)

class GPTConnection:
    def __init__(self, state_obj: State, persona: str, mindmap: str, api_key:str):
        self.state = state_obj
        self.persona = persona
        self.mindmap = mindmap
        
        if not api_key:
            api_key = self.get_key()
        self.set_key(api_key)
    
    def get_key(self):
        if os.path.exists('SECRETKEY'):
            return open('SECRETKEY').read().strip()
    
    def set_key(self, api_key):
        if api_key:
            with open('SECRETKEY', 'w') as fw:
                print(api_key, file=fw)
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
                [{"role": "system", "content": self.persona + self.mindmap}]
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
