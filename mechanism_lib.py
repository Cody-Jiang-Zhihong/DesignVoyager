# Import ChromaDB library for vector database operations
import chromadb

 # Initialize ChromaDB client instance
# This initializes a local vector database client
library_client = chromadb.Client()

# Create a collection named "my_collection"
# Collections store vector data, similar to database tables
collection = library_client.create_collection(name="my_collection")
# code_dict: a global dictionary to store code snippets associated with each document ID
# key: document ID (str), value: code snippet (str)
code_dict = {}

# Add some test mechanisms and code to the database
def set_up_db(collection):
    # Add documents to the database
    # documents: list of text documents to store
    # metadatas: list of metadata dictionaries for each document
    # ids: list of unique identifiers for each document
    collection.add(
        documents=["Players commit a hidden \"quantum\" token whose final resource value is determined by a weighted probability collapse only when revealed during the resolution phase",
                "Placing a piece on the board actively repels all directly adjacent pieces one space outwards, altering the board state dynamically and potentially pushing them off the map"],
        metadatas=[{"mechanic_name": "Quantum Resource Commitment", "mechanic_type": "Hidden Information"}, 
                {"mechanic_name": "Cascade Repulsion Placement", "mechanic_type": "Board Interaction"}],
        ids=["id1", "id2"]
    )

    global code_dict
    code_dict.update({
        "id1": "def quantum_resource_commitment(player_token):\n    # Player commits a hidden token\n    # The final value is determined by a weighted probability collapse\n    pass",
        "id2": "def cascade_repulsion_placement(piece_position):\n    # Place a piece on the board\n    # Repel adjacent pieces\n    pass"
    })

# Function to add new mechanic to the database
def update_library(mechanic_name, mechanic_type, description, python_code):
    global code_dict
    # Determine a unique ID for the new entry
    existing_ids = set(code_dict.keys())
    new_id_prefix = "id"
    new_id = None
    i = 1
    while True:
        candidate_id = f"{new_id_prefix}{i}"
        if candidate_id not in existing_ids:
            new_id = candidate_id
            break
        i += 1

    # Add to the collection and code_dict
    collection.add(
        documents=[description],
        metadatas=[{"mechanic_name": mechanic_name, "mechanic_type": mechanic_type}],
        ids=[new_id]
    )

    code_dict[new_id] = python_code
    return new_id


# Function to retrieve mechanic based on prompt
def retrieve_mechanism(prompt):
    # Query similar documents in the collection
    # query_texts: list of query texts
    # n_results: number of most similar results to return
    results = collection.query(
        query_texts=[prompt],
        n_results=3
    )
    
    # Extract results into a list of dictionaries
    mechanic_list = []
    if results['documents'] and results['documents'][0]:
        for i in range(len(results['documents'][0])):
            doc = results['documents'][0][i]
            meta = results['metadatas'][0][i]
            mechanic_list.append({
                "mechanic_name": meta.get("mechanic_name", "Unknown"),
                "mechanic_type": meta.get("mechanic_type", "Unknown"),
                "id": results['ids'][0][i],
                "description": doc,
                "python_code": code_dict.get(results['ids'][0][i], "No code available")
            })
    return mechanic_list

# Print query results
set_up_db(collection)
results = retrieve_mechanism("quantum token")
print(results)

