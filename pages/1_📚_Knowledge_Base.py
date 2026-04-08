### IMPORT DEPENDENCIES ###

# import basics
import os
import glob
import time
import re
import hashlib

# import streamlit
import streamlit as st

# import langchain
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_openai import OpenAIEmbeddings

# import supabase
from supabase.client import Client, create_client
from postgrest.exceptions import APIError

### SET UP STREAMLIT APP ###

# initiating streamlit app
st.set_page_config(page_title="Agentic RAG Chatbot", 
                   page_icon="ðŸ¤–",
                   layout="wide")

### LOAD CONFIG ###

def get_secret(name):
    if name in st.secrets:
        return st.secrets[name]
    st.error(f"Missing required secret: {name}")
    st.stop()

# Required secrets (set these in .streamlit/secrets.toml)
# SUPABASE_URL = "https://wxcujgciqlqfvmrevvty.supabase.co"
# SUPABASE_SERVICE_KEY = "sb_publishable_OPgvUQjYKdcQc1y2sNF2_Q_a_FA2OOE"
# OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_SERVICE_KEY = get_secret("SUPABASE_SERVICE_KEY")
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")

if "publishable" in SUPABASE_SERVICE_KEY.lower() or "anon" in SUPABASE_SERVICE_KEY.lower():
    st.warning(
        "Your SUPABASE_SERVICE_KEY looks like a publishable/anon key. "
        "Row Level Security may block inserts; use a service role key for ingestion."
    )

SUPABASE_SETUP_SQL = """
create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  embedding vector(3072) not null
);

create index if not exists documents_embedding_idx
on public.documents
using ivfflat (embedding vector_cosine_ops)
with (lists = 100);

create index if not exists documents_metadata_idx
on public.documents
using gin (metadata);

create or replace function public.match_documents(
  query_embedding vector(3072),
  match_count int default 5,
  filter jsonb default '{}'::jsonb
)
returns table (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
)
language sql
stable
as $$
  select
    d.id,
    d.content,
    d.metadata,
    1 - (d.embedding <=> query_embedding) as similarity
  from public.documents d
  where d.metadata @> filter
  order by d.embedding <=> query_embedding
  limit match_count;
$$;
"""

# initiate supabase db
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
except Exception as e:
    st.exception(e)
    st.stop()

# Validate Supabase credentials early so failures are clear before ingestion.
try:
    supabase.from_("documents").select("id").limit(1).execute()
except APIError as e:
    # postgrest APIError carries status code in the payload dict.
    error_text = str(e)
    if "401" in error_text:
        st.error(
            "Supabase authentication failed (401 Invalid API key). "
            "Update SUPABASE_SERVICE_KEY in .streamlit/secrets.toml with a key from this exact Supabase project."
        )
        st.stop()
    if "PGRST205" in error_text or "public.documents" in error_text:
        st.error(
            "Supabase table public.documents is missing in this project. "
            "Run the SQL below in Supabase SQL Editor, then refresh this page."
        )
        st.code(SUPABASE_SETUP_SQL, language="sql")
        st.stop()
    st.exception(e)
    st.stop()
except Exception as e:
    st.exception(e)
    st.stop()

# initiate embeddings model
embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=OPENAI_API_KEY)


# Get the directory where the Streamlit app is running
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Define the persistent storage folder inside the app directory
UPLOAD_DIR = os.path.join(APP_DIR, "documents")

# Ensure the directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Define persistent storage directory for URLs
URL_DIR = os.path.join(APP_DIR, "URLs")

# Ensure the directory exists
os.makedirs(URL_DIR, exist_ok=True)

# Store URLs in a persistent file
url_file_path = os.path.join(URL_DIR, "articles.txt")

# Get the list of existing files in /documents
existing_files = set(os.listdir(UPLOAD_DIR))


def build_storage_filename(original_name):
    """Create a Windows-safe local filename while preserving extension."""
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", original_name).strip().rstrip(".")
    base_name, ext = os.path.splitext(safe_name)
    if not base_name:
        base_name = "upload"

    # Keep path comfortably below Windows MAX_PATH when joined to UPLOAD_DIR.
    max_full_path = 240
    max_base_len = max(20, max_full_path - len(UPLOAD_DIR) - len(ext) - 1)
    if len(base_name) > max_base_len:
        name_hash = hashlib.md5(original_name.encode("utf-8")).hexdigest()[:8]
        trim_len = max_base_len - len(name_hash) - 1
        base_name = f"{base_name[:trim_len]}_{name_hash}"

    candidate = f"{base_name}{ext}"
    counter = 1
    while os.path.exists(os.path.join(UPLOAD_DIR, candidate)):
        candidate = f"{base_name}_{counter}{ext}"
        counter += 1
    return candidate


### SET UP STREAMLIT APP ###

# Add a sidebar
with st.sidebar:
    st.title("Admin Controls")
    
    # Add deletion functionality section
    st.subheader("Delete Knowledge Base")
    
    # Add confirmation checkboxes for safety
    confirm_docs = st.checkbox("I want to delete all documents", key="confirm_docs")
    confirm_urls = st.checkbox("I want to delete all URLs", key="confirm_urls")
    
    # Add delete button that checks for confirmation
    if st.button("Delete Selected Data", key="delete_button"):
        if confirm_docs or confirm_urls:
            if confirm_docs:
                # Delete all files in the documents folder
                for file_path in glob.glob(os.path.join(UPLOAD_DIR, "*")):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        st.error(f"Error deleting {file_path}: {e}")
                st.success("All documents have been deleted!")
                # Reset the existing_files set
                existing_files = set()
            
            if confirm_urls:
                # Delete the URLs file
                if os.path.exists(url_file_path):
                    try:
                        os.remove(url_file_path)
                        # Create an empty file to maintain structure
                        with open(url_file_path, "w") as f:
                            pass
                        st.success("All URLs have been deleted!")
                    except Exception as e:
                        st.error(f"Error deleting URLs file: {e}")
            
            # Add a button to clear the success messages
            if st.button("Clear Messages", key="clear_messages"):
                st.experimental_rerun()
        else:
            st.warning("Please confirm which data you want to delete by checking the boxes above.")


### SET UP FRONT AND BACK END ###

# layout for main page
col_11, col_12 = st.columns([1, 5])

with col_11:
   app_dir = os.path.dirname(os.path.abspath(__file__))
   logo_path = os.path.join(app_dir, "..", "gt_cura_logo.jpg")
   if not os.path.exists(logo_path):
       st.error(f"Logo not found at: {logo_path}")
   else:
       st.image(logo_path)

with col_12:
   st.header('Knowledge Base')

# layout for page fuinctionality
col_21, col_22, col_23 = st.columns([5,1,5])

# Load PDF documents
with col_21:
    st.markdown('### Upload Documents')
    pdf_docs = st.file_uploader('Upload documents and click on "Send & Process"', 
                                accept_multiple_files=True, 
                                key="pdf_uploader")
    
    # Add a placeholder to display processing messages
    message_placeholder = st.empty()

    # cereate a filed upload widget
    if st.button("Send & Process", 
                key="process_button"):
        if not pdf_docs:
            st.warning("Please upload at least one document before processing.")
        else:
            # use spinner widget
            with st.spinner("Processing..."):
                processed_any = False
                for doc in pdf_docs:
                    storage_name = build_storage_filename(doc.name)
                    file_path = os.path.join(UPLOAD_DIR, storage_name)

                    # Check if the file already exists
                    if storage_name in existing_files:
                        message_placeholder.write(f'File "{doc.name}" already exists.\n\n Skipping upload!')
                        time.sleep(3)

                        # clear screen
                        message_placeholder.empty()
                        
                        # Skip to the next file
                        continue
                    
                    # echo messsage to screen 
                    message_placeholder.write(f'Loading file: "{doc.name}"...')

                    # Save uploaded file to persistent storage
                    with open(file_path, "wb") as f:
                        f.write(doc.getbuffer())
                    existing_files.add(storage_name)

                    # Instantiate document loader with the persistent file path
                    loader = PyPDFLoader(file_path)

                    # split the documents in multiple chunks
                    pdf_pages = loader.load()
                    for page in pdf_pages:
                        page.metadata["original_filename"] = doc.name
                        page.metadata["stored_filename"] = storage_name

                    # echo messsage to screen 
                    message_placeholder.write(f'File {doc.name} has {len(pdf_pages)} pages')

                    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
                    chunks = text_splitter.split_documents(pdf_pages)

                    # echo messsage to screen 
                    message_placeholder.write(f'File {doc.name} has {len(chunks)} chunks')

                    # echo messsage to screen 
                    message_placeholder.write(f'Uploading {doc.name} to vector store...')
                    
                    # store chunks in vector store
                    vector_store = SupabaseVectorStore.from_documents(
                        chunks,
                        embeddings,
                        client=supabase,
                        table_name="documents",
                        query_name="match_documents",
                        chunk_size=1000,
                    )

                    # echo messsage to screen 
                    message_placeholder.write(f'File {doc.name} uploaded to vector store')

                    # wait enough time for user to see message
                    time.sleep(3)

                    # clear screen
                    message_placeholder.empty()

                    processed_any = True

                if processed_any:
                    st.success("Documents ingested successfully.")
                    st.rerun()

    # Display available documents in the local file repository
    st.markdown("### Documents in the Vector Store:")

    # List all files in the /documents folder
    all_files = os.listdir(UPLOAD_DIR)
    
    # For document checkboxes
    selected_files = [file for idx, file in enumerate(all_files) if st.checkbox(file, value=True, key=f"doc_{idx}")]

# empty placeholder
with col_22:
    st.write("")

# load web articles
with col_23:
    st.markdown("### Upload Articles")

    # Create a placeholder for the text input
    url_input_placeholder = st.empty()

    # Text input box for entering article URLs
    with url_input_placeholder:
        article_urls = st.text_area("Enter article URLs (one per line)", key="url_input")

    # Read existing URLs from the stored file
    existing_urls = set()
    if os.path.exists(url_file_path):
        with open(url_file_path, "r") as f:
            existing_urls = set(line.strip() for line in f.readlines())

    # Button to process URLs
    if st.button("Send & Process Articles", key="process_articles_button"):
        
        # Split URLs into a list and remove empty lines
        url_list = [url.strip() for url in article_urls.split("\n") if url.strip()]

        if not url_list:
            st.warning("Please enter at least one URL.")
        else:
            # Filter out already uploaded URLs
            new_urls = [url for url in url_list if url not in existing_urls]

            if not new_urls:
                st.warning("All entered URLs have already been uploaded.")
            else:
                with open(url_file_path, "a") as f:
                    for url in new_urls:
                        f.write(url + "\n")
                
                # Clear input field
                url_input_placeholder = st.empty()

                # Process each new article using LangChain WebBaseLoader
                with st.spinner("Processing articles..."):
                    processed_any = False
                    for url in new_urls:
                        loader = WebBaseLoader(url)
                        article_docs = loader.load()

                        # Split documents (if needed)
                        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
                        chunks = text_splitter.split_documents(article_docs)

                        # Store chunks in vector store
                        vector_store = SupabaseVectorStore.from_documents(
                            chunks,
                            embeddings,
                            client=supabase,
                            table_name="documents",
                            query_name="match_documents",
                            chunk_size=1000,
                        )
                        processed_any = True

                if processed_any:
                    st.success("Articles ingested successfully.")
                    st.rerun()

    # Display available articles in the vector store
    st.markdown("### Articles in the Vector Store:")

    # Read and display articles from the stored file
    if os.path.exists(url_file_path):
        with open(url_file_path, "r") as f:
            all_articles = f.readlines()

        # For article checkboxes
        selected_articles = [article.strip() for idx, article in enumerate(all_articles) if st.checkbox(article.strip(), value=True, key=f"article_{idx}")]
