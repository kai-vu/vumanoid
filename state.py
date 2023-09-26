import requests

class State:
    def __init__(self, fname):
        self.fname = fname
        self.actions = {}

    def register_action(self, keyword, action):
        self.actions.setdefault(keyword, []).append(action)
    
    def read(self):
        return open(self.fname).read()

    def log(self, message):
        # Write to log
        with open(self.fname, 'a') as fw:
            print(message, file=fw)
        
        # Do action
        keyword, content = message.split(' ', 1)
        if keyword[0] == '>':
            for action in self.actions.get(keyword[1:]):
                action(content)

    def clear(self):
        open(self.fname, 'w').close()

    @staticmethod
    def input(keyword, content):
        message = f'<{keyword} {content}'
        requests.post('http://127.0.0.1:5000/state', data=message.encode('utf8'))
    
    @staticmethod
    def output(keyword, content):
        message = f'>{keyword} {content}'
        requests.post('http://127.0.0.1:5000/state', data=message.encode('utf8'))