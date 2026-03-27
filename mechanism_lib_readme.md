# Mechanism Library README

## Overview

This module, `mechanism_lib.py`, establishes a vector database for game mechanisms using ChromaDB. It allows for storing, updating, and retrieving game mechanics based on textual descriptions. The primary purpose is to build a searchable library of game mechanisms that can be queried using descriptions from game skeletons, with results formatted to align with proposal module definitions.

## Functions

### `set_up_db(collection)`

**Purpose**: Initializes the database with sample game mechanisms and associated code snippets.

**Parameters**:
- `collection`: The ChromaDB collection object to add data to.

**Usage**:
```python
set_up_db(collection)
```
This function adds predefined documents, metadata, and IDs to the collection, and updates the global `code_dict` with corresponding Python code snippets.

### `update_library(mechanic_name, mechanic_type, description, python_code)`

**Purpose**: Adds a new game mechanism to the database, ensuring unique ID generation.

**Parameters**:
- `mechanic_name` (str): The name of the game mechanic.
- `mechanic_type` (str): The type or category of the mechanic.
- `description` (str): A textual description of the mechanic.
- `python_code` (str): The associated Python code snippet.

**Returns**: The unique ID (str) assigned to the new entry.

**Usage**:
```python
new_id = update_library("New Mechanic", "Action", "Description of the mechanic", "def new_mechanic():\n    pass")
```
This function generates a unique ID, adds the description and metadata to the collection, and stores the Python code in `code_dict`.

### `retrieve_mechanism(prompt)`

**Purpose**: Retrieves up to 3 similar game mechanisms based on a query prompt.

**Parameters**:
- `prompt` (str): The query text, which can directly use descriptions from game skeletons.

**Returns**: A list of dictionaries, each containing:
- `mechanic_name` (str): Name of the mechanic.
- `mechanic_type` (str): Type of the mechanic.
- `id` (str): Unique identifier.
- `description` (str): Full description.
- `python_code` (str): Associated code snippet.

**Usage**:
```python
results = retrieve_mechanism("quantum token")
```
The returned data format is designed to be compatible with proposal module definitions. The query can directly use textual descriptions from game skeletons for seamless integration.