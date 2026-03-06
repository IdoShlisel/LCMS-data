import streamlit as st
import pandas as pd
import functions as f
import classes
import plotly.graph_objects as go

# --- Session State Initialization ---
# Initialize a list to hold the questions if it doesn't exist yet
if 'questions' not in st.session_state:
    st.session_state.questions = [""]

if 'chebi_relations' not in st.session_state:
    st.session_state.chebi_relations = pd.DataFrame()
if 'groq_answers_df' not in st.session_state:
    st.session_state.groq_answers_df = pd.DataFrame()
# Initialize groq_clint as none
if 'groq_clint' not in st.session_state:
    st.session_state.groq_clint = None
# Callbacks to handle dynamic question lists
def add_question():
    st.session_state.questions.append("")

def remove_question(index):
    st.session_state.questions.pop(index)

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("1. Initiate Groq client")
    groq_clint_password = st.text_input("Enter your Groq API Key", type="password").strip()
    
    st.divider()

    st.header("2. Data Input")
    
    # Directly display the text area for pasting the list
    pasted_input = st.text_area("Paste your list (e.g., copied column from Excel)")
    
    # Process the pasted data if it exists
    if pasted_input:
        user_compounds = set(pasted_input.splitlines())
        # Remove any empty lines accidentally captured
        if "" in user_compounds:
            user_compounds.remove("")
    else:
        user_compounds = set()

    st.divider()

    st.header("3. Questions")
    
    # Dynamically render text inputs for each question in the session state
    for i, q in enumerate(st.session_state.questions):
        # Use columns to put the text input and the remove button side-by-side
        col1, col2 = st.columns([5, 1])
        
        with col1:
            # Update the session state list directly as the user types
            st.session_state.questions[i] = st.text_input(
                f"Question {i+1}", 
                value=q, 
                key=f"q_{i}"
            )
            
        with col2:
            # Add vertical spacing to align the button with the text input box
            st.write("")
            st.write("")
            # Delete button uses a callback to remove the item and trigger a rerun
            st.button(
                "❌", 
                key=f"del_{i}", 
                help="Remove this question", 
                on_click=remove_question, 
                args=(i,)
            )

    # Add question button uses a callback to append an empty string
    st.button("➕ Add Question", on_click=add_question)

    st.divider()

    # --- Run Button ---
    # The button returns True only on the exact interaction frame it was clicked
    run_button = st.button("🚀 Run Calculation", type="primary", use_container_width=True)


######################3 --- Main Screen ###################################################3

st.title("🧪 LCMS Molecule Analyzer")

## folded instructions:


with st.expander("📖 How to use this app (Documentation)"):
    st.markdown("""
    ## 🌟 Overview
    This application helps you find information about molecules from LCMS results by:
    1. **Comparing results** to the [ChEBI database](https://www.ebi.ac.uk/chebi/).
    2. **Using Groq LLM** to answer specific questions about each molecule.

    ---
    ## 🛠 Instructions
    1. **Enter your Groq API Key** in the sidebar.
    2. **Paste molecule names** from your LCMS file.
    3. **Configure AI Analysis**:
        * Ask open-ended or Yes/No questions.
        * Select as many questions as you need.
        * *Note: More questions = longer processing time!* ⏳
    
    4. **Download results** as a CSV file once finished. 📥
    """)


if run_button:

    #### logic ##### 
    #1. initiate groq clint
    try:
        st.session_state.groq_clint = f.init_groq_client(groq_clint_password)
        st.success("Groq client initialized successfully.")
    except Exception as e:
        st.error(f"Failed to initialize Groq client: {e}")
        st.stop()  # Stop execution if the client cannot be initialized

    #2. build molecule objects

    #2.1 get questions 
      # Filter out empty strings before processing
    valid_questions = [q for q in st.session_state.questions if q.strip() != ""]
    # show the valid questions in a dataframe for user review
    questions_dict = {f.groq_question_summary(q, client=st.session_state.groq_clint): q for i, q in enumerate(valid_questions)}
    # Convert to DataFrame (orient='index' maps keys to rows)
    df = pd.DataFrame.from_dict(questions_dict, orient='index', columns=['user question'])
    # 2. Rename the Index to "question columns name"
    df.index.name = "question columns name"
    st.dataframe(df, use_container_width=True)
    


    #2.2 build molecule objects and ask groq questions and get chebi relations
    compounds = dict()

    # 2.2.1 Create a status container to show logs
    with st.status("Analyzing compounds...", expanded=True) as status:
        
        # 2.2.2 Initialize the progress bar
        progress_bar = st.progress(0, text="Processing compounds...")
        total_compounds = len(user_compounds)
        # Loop over the compounds and process them
        for i, compound_name in enumerate(user_compounds):
            
            comp = classes.compound(compound_name)
            # update status if a compound dose not have chebi id
            if comp.chebi_id is None:
                status.warning(f"Compound '{compound_name}' does not have a ChEBI ID. Skipping ChEBI relations.")
            # ask groq questions 
            for question_title, question in questions_dict.items():
                comp.ask_groq_questions(client=st.session_state.groq_clint, user_prompt=question, 
                                        user_question_title=question_title
                                        )
            # get chebi relations data
            comp.set_chebi_relations()
            compounds[comp.name] = comp
            # ---------------------------
            # 2.2.3. Update the progress bar (0.0 to 1.0)
            progress_val = (i + 1) / total_compounds
            progress_bar.progress(progress_val)

        # 2.2.4. Finalize the status once the loop ends
        status.update(label="✅ Analysis Complete!", state="complete", expanded=False)

    st.success(f"Successfully processed {len(compounds)} compounds.", icon="✅")

    st.session_state.compounds = compounds  # Store the compounds in session state for later use

    # 1. Build the Groq Answers DataFrame using a list of dicts
    groq_data = [
        {"Compound": name, "Question": q, "Answer": a}
        for name, obj in compounds.items()
        for q, a in obj.groq_questions.items()
    ]
    df_groq_raw = pd.DataFrame(groq_data)

    # Best Practice: Pivot so each question is a column
    if not df_groq_raw.empty:
        groq_answers_df = df_groq_raw.pivot(
            index="Compound", 
            columns="Question", 
            values="Answer"
        ).reset_index()
    else:
        groq_answers_df = pd.DataFrame(columns=["Compound"])
    st.session_state.groq_answers_df = groq_answers_df  # Store in session state for later use
    # 2. Build the ChEBI Relations DataFrame
    chebi_df = pd.DataFrame()
    for name, obj in compounds.items():
        # Only process if chebi_relations exists and isn't empty
        if getattr(obj, 'chebi_relations', None) is not None and not obj.chebi_relations.empty:
            # Extract the columns we need from the existing internal DataFrame
            temp_df = obj.chebi_relations.copy()
            temp_df['Compound'] = name
            chebi_df = pd.concat([chebi_df, temp_df], ignore_index=True)
    
    #rename columns
    chebi_df = chebi_df.drop(columns=['outgoing_relations.init_id', 'outgoing_relations.final_id'], errors='ignore')  # Drop if exists
    chebi_df = chebi_df.rename(columns={
        'Compound': 'LCMS Compound Name',
        'outgoing_relations.init_name': 'ChEBI database Name',
        'outgoing_relations.relation_type': 'ChEBI Relation Type',
        'outgoing_relations.final_name': 'ChEBI Relattion'
    })
    #make LCMS Compound Name be the first column
    chebi_df = chebi_df[['LCMS Compound Name'] + [col for col in chebi_df.columns if col != 'LCMS Compound Name']]

    st.session_state.chebi_relations = chebi_df  # Store in session state for later use



    # 4. Display the results
    st.subheader("Groq Questions and Answers")
    st.dataframe(st.session_state.groq_answers_df, use_container_width=True, hide_index=True, column_config={"Compound": st.column_config.TextColumn("Compound Name")})

    st.subheader("ChEBI Relations")
    #show chart of chebi_df with filter on relation type

    # 1. Multi-select for Relation Type (Default is all options)
    all_relation_types = st.session_state.chebi_relations['ChEBI Relation Type'].unique().tolist()

    relation_type_filter = st.multiselect(
        "Filter by Relation Type", 
        options=all_relation_types,
        default=all_relation_types 
    )

    # Filter the dataframe based on the multi-select choices
    if relation_type_filter:
        filtered_chebi_df = st.session_state.chebi_relations[
            st.session_state.chebi_relations['ChEBI Relation Type'].isin(relation_type_filter)
        ]
    else:
        filtered_chebi_df = st.session_state.chebi_relations.iloc[0:0]

    # 2. Pre-process the data
    if not filtered_chebi_df.empty:
        df_grouped = filtered_chebi_df.groupby(['ChEBI Relation Type', 'ChEBI Relattion'])['LCMS Compound Name'].agg(
            unique_count='nunique',
            molecule_list=lambda x: '<br>'.join(x.unique())
        ).reset_index()
        
        # CRITICAL: Sort by outer then inner to ensure the nested X-axis brackets group cleanly together
        df_grouped = df_grouped.sort_values(by=['ChEBI Relation Type', 'ChEBI Relattion'])
        
        # Create colors so each 'Relation Type' block gets its own color like JMP
        unique_outer = df_grouped['ChEBI Relation Type'].unique()
        colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52']
        color_map = {cat: colors[i % len(colors)] for i, cat in enumerate(unique_outer)}
        marker_colors = [color_map[cat] for cat in df_grouped['ChEBI Relation Type']]

        # To build a JMP-style nested axis, we must pass a 2-level array to X
        x_multi = [
            df_grouped['ChEBI Relation Type'].tolist(), # Outer Category
            df_grouped['ChEBI Relattion'].tolist()      # Inner Category
        ]
        
        # 3. Create the Chart using Graph Objects (go) instead of Express (px)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=x_multi,
            y=df_grouped['unique_count'].tolist(),
            customdata=df_grouped['molecule_list'].tolist(),
            marker_color=marker_colors,
            # Format the hover text: %{x[0]} is outer, %{x[1]} is inner category
            hovertemplate="<b>%{x[0]}</b> > %{x[1]}<br><b>Count:</b> %{y}<br><br><b>Molecules:</b><br>%{customdata}<extra></extra>"
        ))
        
        # 4. Force the nested layout without a legend
        fig.update_layout(
            showlegend=False,          # Removes the legend completely
            bargap=0.05,               # Tightens the bars to create a histogram appearance
            xaxis=dict(
                type='multicategory',  # Forces the 2-level nested axis!
                title=""               # Removes title so the bracket labels stand on their own
            ),
            yaxis_title="Count of Distinct Compounds",
            title="Count of Distinct Compounds by Relation Hierarchy"
        )
        
        st.plotly_chart(fig, use_container_width=True, theme="streamlit", config={"displayModeBar": False})
    else:
        st.info("Please select at least one Relation Type to display the chart.")
    #show ChEBI df
    st.dataframe(filtered_chebi_df, use_container_width=True, hide_index=True)

    # 5. Provide download buttons for the results
    st.subheader("Download Results")
    # merge both dfs by LCMS Compound Name
    if not st.session_state.groq_answers_df.empty and not st.session_state.chebi_relations.empty:
        merged_df = pd.merge(st.session_state.groq_answers_df, st.session_state.chebi_relations, left_on="Compound", right_on="LCMS Compound Name", how="outer")
        # Drop the redundant 'LCMS Compound Name' column after merge
        merged_df = merged_df.drop(columns=['LCMS Compound Name'], errors='ignore')
        st.download_button(
            label="Download Merged Data as CSV",
            data=merged_df.to_csv(index=False).encode('utf-8'),
            file_name='merged_compound_data.csv',
            mime='text/csv'
        )
    else:
        st.info("No data available to download.")    



else:
    st.info("Awaiting input. Configure parameters in the sidebar and click Run.")


