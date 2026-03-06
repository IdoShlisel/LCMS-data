import requests
import pandas as pd
from groq import Groq
import json

def get_chebi_outgoing_relations(chebi_id, timeout=10, relation_type="has role"):
    # Standardize the ID
    chebi_id=str(chebi_id)  # Ensure it's a string
    if not chebi_id.startswith("CHEBI:"):
        chebi_id = f"CHEBI:{chebi_id}"
    
    # Use the PARENTS endpoint to match the "Outgoing" section on the web
    url = f"https://www.ebi.ac.uk/chebi/backend/api/public/ontology/parents/{chebi_id}/"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        parents = response.json()
    except Exception as e:
        print(f"Request failed: {e}")

    data=pd.DataFrame(parents["ontology_relations"])
    data = pd.json_normalize(data.to_dict(orient='records')) 

    if relation_type:
        data = data[data['outgoing_relations.relation_type'] == relation_type]
    return data       




def init_groq_client_file(password_file='groq_password.json'):
    with open(password_file, 'r') as fh:
        groq_password = json.load(fh)      
    groq_password=groq_password["password"]
    client = Groq(api_key=groq_password)
    return client


def init_groq_client(groq_password=None):
    if groq_password is None:
        raise ValueError("Groq API key must be provided")  
    client = Groq(api_key=groq_password)
    return client



def ask_groq(molecule, client, user_prompt, temp=0.0, max_tokens=100):
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
        {
            "role": "system",
            "content":
             """You are a chemistry professor and molecular analysis expert.
            Your task is to determine whether a specific molecule appears in the context described in the user’s question.

            Rules:
            - Use established chemical knowledge.
            - Answer concisely and professionally.
            - Do not explain your reasoning.
            - Return exactly one line.
            - if the answer is not clear from the question, answer "Unknown".
            - if the question can answer in yes or no, answer with "Yes" or "No".
            - do not end your answer with a period.
            - do not mention the molecule name in your answer.
        Output format:
        A very short professional answer.

            """
        },
        {
            "role": "user",
            "content": 
            f"for the molecule: {molecule}, the question is: {user_prompt}"
        },



    ],
            temperature=temp, # Lower temperature for factual accuracy
            max_tokens=max_tokens
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"
    
def read_file(path):

    df = pd.read_excel(path, sheet_name="Compounds")
    unique_compounds = df['Name'].unique().tolist()
    return df, unique_compounds

def get_chebi_id(molecule_name: str) -> str:
    """
    Fetches the ChEBI ID for a given molecule name using the EBI OLS API.
    
    Args:
        molecule_name (str): The name of the molecule (e.g., "water", "glucose").
        
    Returns:
        str: The ChEBI ID (e.g., "CHEBI:15377") or None if not found.
    """
    base_url = "https://www.ebi.ac.uk/ols4/api/search"
    
    # Parameters for an exact match search
    params = {
        "q": molecule_name,
        "ontology": "chebi",
        "queryFields": "label,synonym",
        "exact": "true"
    }
    
    try:
        # 1. Try an exact match first
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        docs = data.get("response", {}).get("docs", [])
        if docs:
            return docs[0].get("obo_id")  # e.g., CHEBI:15377
            
        # 2. If no exact match, try a fuzzy search
        params["exact"] = "false"
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        docs = data.get("response", {}).get("docs", [])
        if docs:
            # Return the top hit from the fuzzy search
            return docs[0].get("obo_id")
            
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        
    return None


def groq_question_summary(user_question, client, temp=0.0, max_tokens=100):
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
        {
            "role": "system",
            "content":
             """your task is to summarize the following question in 1-4 words, keeping only the main point of the question and removing any unnecessary details.
               The summary should be concise and capture the essence of the original question.
            Output format:
            summary of 1-4 words.

            Where:
            every word is concatenated with "_".

            example:

            user question: "What is the role of this molecule?"
            summary: "molecule_role"

            """
        },
        {
            "role": "user",
            "content": 
            user_question
        }


    ],
            temperature=temp, # Lower temperature for factual accuracy
            max_tokens=max_tokens
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"
    
