import streamlit as st
import requests
from application import client, connect_api, api_client
from io import StringIO
import pandas as pd
import concurrent.futures


if client.WellKnownApi(api_client).get_well_known_health() != "ok":
    raise ConnectionError("Please open the pieces server")


extensions = [e.value for e in client.ClassificationSpecificEnum]
opensource_application = connect_api()
models_api = client.ModelsApi(api_client)
# Get models from Client
api_response = models_api.models_snapshot()
models = {model.name: model.id for model in api_response.iterable if model.cloud or model.downloaded}

# Set default model from Client
default_model_name = "GPT-4 Chat Model"
model_id = models[default_model_name]
models_name = list(models.keys())
default_model_index = models_name.index(default_model_name)

new = ''

# Web App UI 
st.title("Pieces Model Eval app")

st.sidebar.title("Choose a model")
model_name = st.sidebar.selectbox("Choose a model", models_name, index=default_model_index)

# Get prompt from user
prompt = st.text_area("Enter your prompt", "Act as a programmer and generate a README text for a project in less than 50 words")

# Ask user if they want to upload a file
upload_file = st.sidebar.radio("Do you want to upload a file?", ("No", "Yes"))

files = []
if upload_file == "Yes":
    files = st.file_uploader("Upload a file", accept_multiple_files=True)

# Function to send request to the /qgpt/question endpoint
def get_model_response(model_name, model_id, prompt, iterable):
    question = client.QGPTQuestionInput(
        query=prompt,
        relevant=client.RelevantQGPTSeeds(iterable=iterable) if iterable else {"iterable": []},
        model=model_id
    )

    question_json = question.to_json()

    # Send a Prompt request to the /qgpt/question endpoint
    response = requests.post('http://localhost:1000/qgpt/question', data=question_json)

    try:
        # Create an Instance of Question Output 
        question_output = client.QGPTQuestionOutput(**response.json())

        # Getting the answer
        answers = question_output.answers.iterable[0].text
        return {"Model": model_name, "Response": answers}
    except requests.exceptions.JSONDecodeError:
        return {"Model": model_name, "Response": "Failed to decode JSON response"}
    except Exception as e:
        return {"Model": model_name, "Response": f"An error occurred: {str(e)}"}

# Create a button for the user to generate a response
if st.button('Generate'):
    with st.spinner('Generating response from models...'):
        iterable = []
        if files:
            for file in files:
                if file.name.split(".")[-1] not in extensions:
                    st.warning(f"File type {file.name.split('.')[-1]} not supported.")
                    files.remove(file)  # Remove the file from the list of the files because it is not valid
                    metadata = None
                else:
                    metadata = client.FragmentMetadata(ext=file.name.split(".")[-1])
                try:
                    raw = StringIO(file.getvalue().decode("utf-8"))
                except:
                    st.warning(f"Error in decoding file {file.name}")
                    files.remove(file)  # Remove the file from the list of the files because it is not valid
                    continue
                iterable.append(client.RelevantQGPTSeed(
                    seed=client.Seed(
                        type="SEEDED_ASSET",
                        asset=client.SeededAsset(
                            application=opensource_application,
                            format=client.SeededFormat(
                                fragment=client.SeededFragment(
                                    string=client.TransferableString(raw=raw.read()),
                                    metadata=metadata,
                                ),
                            )))))

        results = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(get_model_response, model_name, model_id, prompt, iterable) for model_name, model_id in models.items()]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        # Convert results to a DataFrame and display as a table
        df = pd.DataFrame(results)
        st.table(df)