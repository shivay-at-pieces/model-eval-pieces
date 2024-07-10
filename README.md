# Pieces Models Evaluation Generator App

This project is a Streamlit-based web application that evaulates the performance of the models that Pieces supports and compares the responses based on a given prompt. You can add a simple text prompt and also file based prompt to add to relevance

## Table of Contents
- [Installation](#installation)
- [Setup](#setup)
- [Usage](#usage)
- [Contributing](#contributing)
- [Credits](#credits)
- [License](#license)

## Installation

### Prerequisites
- Python 3.11
- Streamlit
- Requests
- Pandas
- pieces_os_client

### Steps
1. Clone the repository:
    ```sh
    git clone <repository_url>
    cd <repository_directory>
    ```

2. Create a virtual environment:
    ```sh
    python3 -m venv venv
    source venv/bin/activate  # On Windows use venv\Scripts\activate
    ```

3. Install the required packages:
    ```sh
    pip install streamlit requests pandas pieces_os_client
    ```

## Setup

1. Ensure that the Pieces server is running and accessible at http://localhost:1000.

2. The `application.py` file contains the configuration for the AI client and a function to connect to the API based on the operating system.

    ```python
    import platform
    import pieces_os_client as client

    # AI Client Configuration
    configuration = client.Configuration(host="http://localhost:1000")
    api_client = client.ApiClient(configuration)

    def categorize_os():
        # Get detailed platform information
        platform_info = platform.platform()

        # Categorize the platform information into one of the four categories
        if 'Windows' in platform_info:
            os_info = 'WINDOWS'
        elif 'Linux' in platform_info:
            os_info = 'LINUX'
        elif 'Darwin' in platform_info:  # Darwin is the base of macOS
            os_info = 'MACOS'
        else:
            os_info = 'WEB'  # Default to WEB if the OS doesn't match others

        return os_info

    def connect_api() -> client.Application:
        # Decide if it's Windows, Mac, Linux or Web
        local_os = categorize_os()

        api_instance = client.ConnectorApi(api_client)
        seeded_connector_connection = client.SeededConnectorConnection(
            application=client.SeededTrackedApplication(
                name=client.ApplicationNameEnum.OPEN_SOURCE,
                platform=local_os,
                version="0.0.1"))
        api_response = api_instance.connect(seeded_connector_connection=seeded_connector_connection)
        application = api_response.application
        return application
    ```

3. The `streamlit.py` file contains the Streamlit application code.

    ```python
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
    st.title("Pieces Model Eval Generator app")

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

    # Create a button for the user to generate 
    if st.button('Generate'):
        with st.spinner('Generating model responses...'):
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
    ```

## Usage

1. Run the Streamlit application:
    ```sh
    streamlit run streamlit.py
    ```

2. Open your web browser and go to http://localhost:8501.

3. Upload the files you want to use for generating the model responses.

4. Click the "Generate" button to generate the result text using different models.

5. The results will be displayed in a table with the model names and their corresponding responses.

## Contributing

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-branch`).
3. Make your changes.
4. Commit your changes (`git commit -m 'Add some feature'`).
5. Push to the branch (`git push origin feature-branch`).
6. Open a pull request.

## Credits

- [Your Name](https://github.com/yourusername)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
