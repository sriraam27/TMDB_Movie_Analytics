# Reel Insights: Global Movie Industry (TMDB)

## Run locally
1. Install Python 3.10 or newer.
2. Open a terminal in this project folder.
3. Install dependencies: `pip install -r requirements.txt`
4. Start the dashboard: `streamlit run app.py`

The app uses `data/tmdb.db` when present and otherwise reads the six cleaned CSV files from `data/cleaned/`.

## Required project structure
```text
TMDB_Movie_Analytics/
├── app.py
├── requirements.txt
├── README.md
├── data/
│   ├── six original CSV files
│   ├── tmdb.db
│   └── cleaned/ (six cleaned CSV files)
└── notebooks/
    ├── 01_data_cleaning.ipynb
    ├── 02_sql_analysis.ipynb
    ├── 03_pandas_analysis.ipynb
    └── 04_visualizations.ipynb
```

## Notebook execution order
Run `01_data_cleaning.ipynb`, `02_sql_analysis.ipynb`, `03_pandas_analysis.ipynb`, then `04_visualizations.ipynb`.

## Streamlit features
- Filters page with shared, session-persistent genre, release-year, minimum-rating and original-language filters.
- Dashboard with the four required KPIs, top 10 revenue chart, genre distribution, budget-versus-revenue scatter plot and a selection insight.
- Query Explorer with all ten SQL questions from the GUVI brief, a result table, chart and insight. Queries run against the currently filtered movie selection.

## Top five insights and recommendations
Replace this section with five verified insights and recommendations from the final notebook outputs before submission. Do not submit placeholder findings.
