import functions as f
import pandas as pd

class compound:
    def __init__(self, compound_name):
        self.name = compound_name
        self.groq_questions = dict()
        self.chebi_id = f.get_chebi_id(compound_name)
        self.chebi_relations = None

        

    def ask_groq_questions(self, client, user_prompt, temp=0.2, max_tokens=100, user_question_title=None):
        groq_response = f.ask_groq(client=client, molecule=self.name, user_prompt=user_prompt, temp=temp, max_tokens=max_tokens)
        if user_question_title:
            self.groq_questions[user_question_title] = groq_response
        else:
            self.groq_questions[user_prompt] = groq_response
        return 
    

    def set_chebi_relations(self, relation_type=None):
        if self.chebi_id==None:
            print(f"Could not find ChEBI ID for {self.name}")
            self.chebi_relations = pd.DataFrame()
            return

        self.chebi_relations = f.get_chebi_outgoing_relations(chebi_id=self.chebi_id, relation_type=relation_type)
        return
    
