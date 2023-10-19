import json
import logging

log = logging.getLogger(__name__)

class MindMup:
    def __init__(self, json_file):
        self.json_file = json_file

    def parse(self):
        try:
            with open(self.json_file, 'r') as file:
                data = json.load(file)
                return self.extract_triples(data['ideas'])
        except FileNotFoundError:
            print(f"Error: JSON file '{self.json_file}' not found.")
            return ""

    def extract_triples(self, idea_dict, parent=None):
        triples = ""
        for key, idea in idea_dict.items():
            object_ = idea['title']
            if not object_:
                log.info(f'untitled box encountered, skipping triple')
                continue
            if parent:
                predicate = self.get_predicate(idea)
                subject = parent
                if not predicate: predicate = '->'
                triples += "{} {} {}.\n".format(subject, predicate, object_ )
            if 'ideas' in idea:
                triples += (self.extract_triples(idea['ideas'], object_))
        return triples

    def get_predicate(self, idea):
        if 'attr' in idea:
            if 'parentConnector' in idea['attr']:
                label = idea['attr']['parentConnector'].get('label', '->')
                return label
        else:
            return '->'

# Usage
if __name__ == "__main__":
    json_file = 'mindmup/tutorial.mup'  # Replace with the path to your JSON file
    mindmup_parser = MindMup(json_file)
    triples = mindmup_parser.parse()
    print(triples)
