"""Reel Insights: TMDB movie analytics Streamlit application."""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Reel Insights | TMDB Analytics", page_icon="🎬", layout="wide")

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CLEANED = DATA / "cleaned"
DB = DATA / "tmdb.db"
TABLES = ["movies", "genres", "movie_genres", "cast", "crew", "movie_keywords"]


@st.cache_resource
def get_connection():
    """Open the project database in read-only mode."""
    if not DB.exists():
        return None
    return sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True, check_same_thread=False)


@st.cache_data
def load_table(name):
    """Load one approved table from SQLite, falling back to its cleaned CSV."""
    if name not in TABLES:
        raise ValueError(f"Invalid table name: {name}")
    conn = get_connection()
    if conn is not None:
        try:
            return pd.read_sql_query(f'SELECT * FROM "{name}"', conn)
        except Exception:
            pass
    csv_file = CLEANED / f"{name}_cleaned.csv"
    if csv_file.exists():
        return pd.read_csv(csv_file)
    raise FileNotFoundError(
        f"Could not load '{name}'. Expected table in {DB} or file {csv_file}."
    )


@st.cache_data
def load_data():
    """Load all six tables and prepare movie fields used by the dashboard."""
    data = {name: load_table(name) for name in TABLES}
    movies_df = data["movies"].copy()
    movies_df["release_date"] = pd.to_datetime(movies_df["release_date"], errors="coerce")
    movies_df["release_year"] = movies_df["release_date"].dt.year
    numeric_columns = ["runtime", "budget", "revenue", "popularity", "vote_average", "vote_count"]
    for column in numeric_columns:
        movies_df[column] = pd.to_numeric(movies_df[column], errors="coerce")
    data["movies"] = movies_df
    return data


def money(value):
    """Format a numeric USD value for display."""
    return "N/A" if pd.isna(value) else f"${value:,.0f}"


def filter_movies(frame, years, selected_genres, rating_min, selected_language):
    """Apply the shared app filters to the movie table."""
    result = frame[frame["release_year"].isin(years)].copy()
    result = result[result["vote_average"] >= rating_min]
    if selected_language != "All":
        result = result[result["original_language"].fillna("Unknown") == selected_language]
    if selected_genres:
        genre_movie_ids = movie_genres.merge(genres, on="genre_id", how="inner")
        matching_ids = genre_movie_ids.loc[
            genre_movie_ids["genre_name"].isin(selected_genres), "movie_id"
        ].unique()
        result = result[result["movie_id"].isin(matching_ids)]
    return result


def make_filtered_sql_connection(filtered_frame):
    """Create an in-memory SQL view of the current filtered selection.

    The original project database remains untouched. Related tables are restricted
    to the selected movie IDs so Query Explorer follows the shared filters.
    """
    conn = sqlite3.connect(":memory:")
    selected_ids = set(filtered_frame["movie_id"].dropna().tolist())
    filtered_tables = {
        "movies": filtered_frame.drop(columns=["release_year"], errors="ignore"),
        "genres": genres,
        "movie_genres": movie_genres[movie_genres["movie_id"].isin(selected_ids)],
        "cast": cast[cast["movie_id"].isin(selected_ids)],
        "crew": crew[crew["movie_id"].isin(selected_ids)],
        "movie_keywords": movie_keywords[movie_keywords["movie_id"].isin(selected_ids)],
    }
    for table_name, frame in filtered_tables.items():
        frame.to_sql(table_name, conn, index=False, if_exists="replace")
    return conn


try:
    D = load_data()
    movies = D["movies"]
    genres = D["genres"]
    movie_genres = D["movie_genres"]
    cast = D["cast"]
    crew = D["crew"]
    movie_keywords = D["movie_keywords"]
except Exception as error:
    st.error("Could not load the project data. Check the project folder structure.")
    st.code(
        "TMDB_Movie_Analytics/\n"
        "  app.py\n"
        "  data/\n"
        "    tmdb.db\n"
        "    cleaned/\n"
        "      movies_cleaned.csv\n"
        "      genres_cleaned.csv\n"
        "      movie_genres_cleaned.csv\n"
        "      cast_cleaned.csv\n"
        "      crew_cleaned.csv\n"
        "      movie_keywords_cleaned.csv"
    )
    st.exception(error)
    st.stop()

# Saved SQL analyses cover all ten questions from the GUVI project document.
SQL_QUERIES = {
    "1. Action movies released after 2015": """
        SELECT DISTINCT m.title, m.release_date
        FROM movies m
        JOIN movie_genres mg ON m.movie_id = mg.movie_id
        JOIN genres g ON mg.genre_id = g.genre_id
        WHERE g.genre_name = 'Action' AND CAST(strftime('%Y', m.release_date) AS INTEGER) > 2015
        ORDER BY m.release_date
    """,
    "2. Top 10 highest-grossing movies with genres": """
        SELECT m.title, m.revenue,
               GROUP_CONCAT(DISTINCT g.genre_name) AS genres
        FROM movies m
        LEFT JOIN movie_genres mg ON m.movie_id = mg.movie_id
        LEFT JOIN genres g ON mg.genre_id = g.genre_id
        WHERE m.revenue > 0
        GROUP BY m.movie_id, m.title, m.revenue
        ORDER BY m.revenue DESC LIMIT 10
    """,
    "3. Average budget and revenue by genre": """
        SELECT g.genre_name,
               ROUND(AVG(CASE WHEN m.budget > 0 THEN m.budget END), 2) AS average_budget,
               ROUND(AVG(CASE WHEN m.revenue > 0 THEN m.revenue END), 2) AS average_revenue,
               COUNT(DISTINCT m.movie_id) AS movie_count
        FROM movies m
        JOIN movie_genres mg ON m.movie_id = mg.movie_id
        JOIN genres g ON mg.genre_id = g.genre_id
        GROUP BY g.genre_id, g.genre_name
        ORDER BY average_revenue DESC
    """,
    "4. Top 10 actors by movie appearances": """
        SELECT actor_name, COUNT(DISTINCT movie_id) AS movie_count
        FROM cast
        GROUP BY person_id, actor_name
        ORDER BY movie_count DESC, actor_name LIMIT 10
    """,
    "5. Directors with more than 3 movies": """
        SELECT person_name AS director, COUNT(DISTINCT movie_id) AS movie_count
        FROM crew
        WHERE LOWER(job) = 'director'
        GROUP BY person_id, person_name
        HAVING COUNT(DISTINCT movie_id) > 3
        ORDER BY movie_count DESC, director
    """,
    "6. Top 10 most frequently used keywords": """
        SELECT keyword_name, COUNT(DISTINCT movie_id) AS movie_count
        FROM movie_keywords
        GROUP BY keyword_id, keyword_name
        ORDER BY movie_count DESC LIMIT 10
    """,
    "7. Above-average budget and below-average revenue": """
        SELECT title, budget, revenue
        FROM movies
        WHERE budget > (SELECT AVG(budget) FROM movies WHERE budget > 0)
          AND revenue > 0
          AND revenue < (SELECT AVG(revenue) FROM movies WHERE revenue > 0)
        ORDER BY budget DESC
    """,
    "8. Actors in Christopher Nolan movies": """
        SELECT DISTINCT c.actor_name, m.title
        FROM cast c
        JOIN movies m ON c.movie_id = m.movie_id
        JOIN crew cr ON m.movie_id = cr.movie_id
        WHERE LOWER(cr.job) = 'director'
          AND LOWER(cr.person_name) = 'christopher nolan'
        ORDER BY m.title, c.actor_name
    """,
    "9. Highest-rated genre (at least 20 movies)": """
        SELECT g.genre_name, COUNT(DISTINCT m.movie_id) AS movie_count,
               ROUND(AVG(m.vote_average), 3) AS average_rating
        FROM movies m
        JOIN movie_genres mg ON m.movie_id = mg.movie_id
        JOIN genres g ON mg.genre_id = g.genre_id
        GROUP BY g.genre_id, g.genre_name
        HAVING COUNT(DISTINCT m.movie_id) >= 20
        ORDER BY average_rating DESC
    """,
    "10. Top 10 movies by number of keywords": """
        SELECT m.title, COUNT(DISTINCT mk.keyword_id) AS keyword_count
        FROM movies m
        JOIN movie_keywords mk ON m.movie_id = mk.movie_id
        GROUP BY m.movie_id, m.title
        ORDER BY keyword_count DESC, m.title LIMIT 10
    """,
}

# Sidebar navigation and shared filters. Widget keys persist in st.session_state.
st.sidebar.title("🎬 Reel Insights")
st.sidebar.caption("Global Movie Industry Analytics")
page = st.sidebar.radio(
    "Navigate", ["Filters", "Dashboard", "Query Explorer", "About Project"], key="navigation_page"
)
st.sidebar.divider()
st.sidebar.subheader("Shared filters")

year_values = sorted(movies["release_year"].dropna().astype(int).unique().tolist())
if not year_values:
    st.error("No valid release years were found in the movies dataset.")
    st.stop()
genre_values = sorted(genres["genre_name"].dropna().unique().tolist())
language_values = sorted(movies["original_language"].dropna().astype(str).unique().tolist())

st.sidebar.slider(
    "Release year range", min_value=int(min(year_values)), max_value=int(max(year_values)),
    value=(int(min(year_values)), int(max(year_values))), key="filter_year_range"
)
st.sidebar.multiselect("Genre", genre_values, key="filter_genres")
st.sidebar.slider("Minimum rating", min_value=0.0, max_value=10.0, value=0.0,
                  step=0.1, key="filter_rating")
st.sidebar.selectbox("Original language", ["All"] + language_values, key="filter_language")

selected_years = list(range(st.session_state.filter_year_range[0], st.session_state.filter_year_range[1] + 1))
filtered = filter_movies(
    movies, selected_years, st.session_state.filter_genres,
    st.session_state.filter_rating, st.session_state.filter_language
)
filtered_ids = set(filtered["movie_id"].dropna().tolist())
filtered_genres = movie_genres[movie_genres["movie_id"].isin(filtered_ids)].merge(genres, on="genre_id")
filtered_cast = cast[cast["movie_id"].isin(filtered_ids)]

st.sidebar.metric("Movies matching filters", f"{filtered.movie_id.nunique():,}")

if page == "Filters":
    st.title("Filters")
    st.caption("These selections are shared across the Dashboard and Query Explorer.")
    st.write("Adjust the filters in the sidebar. Your selections are saved in the app session.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Matching movies", f"{filtered.movie_id.nunique():,}")
    c2.metric("Genres represented", f"{filtered_genres.genre_name.nunique():,}")
    c3.metric("Actors represented", f"{filtered_cast.actor_name.nunique():,}")
    c4.metric("Average rating", f"{filtered.vote_average.mean():.2f}" if filtered.vote_average.notna().any() else "N/A")
    st.subheader("Current filter selection")
    st.write(f"**Release years:** {st.session_state.filter_year_range[0]}–{st.session_state.filter_year_range[1]}")
    st.write("**Genres:** " + (", ".join(st.session_state.filter_genres) if st.session_state.filter_genres else "All genres"))
    st.write(f"**Minimum rating:** {st.session_state.filter_rating:.1f}")
    st.write(f"**Original language:** {st.session_state.filter_language}")
    st.subheader("Matching movies")
    st.dataframe(filtered[["title", "release_year", "original_language", "vote_average", "popularity"]].head(1000),
                 use_container_width=True, hide_index=True)
    st.caption("The table displays up to 1,000 matching rows. Use the Dashboard or Query Explorer for analysis.")

elif page == "Dashboard":
    st.title("Reel Insights: Global Movie Industry")
    st.caption("Interactive exploratory analysis of the TMDB movie dataset.")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total movies", f"{filtered.movie_id.nunique():,}")
    k2.metric("Total genres represented", f"{filtered_genres.genre_name.nunique():,}")
    k3.metric("Total actors", f"{filtered_cast.actor_name.nunique():,}")
    k4.metric("Average rating", f"{filtered.vote_average.mean():.2f}" if filtered.vote_average.notna().any() else "N/A")

    left, right = st.columns(2)
    top_revenue = filtered[filtered["revenue"] > 0].nlargest(10, "revenue")
    if not top_revenue.empty:
        left.plotly_chart(
            px.bar(top_revenue.sort_values("revenue"), x="revenue", y="title", orientation="h",
                   title="Top 10 movies by revenue", labels={"revenue": "Revenue (USD)", "title": "Movie"}),
            use_container_width=True
        )
    else:
        left.info("No movies with recorded positive revenue match the current filters.")

    genre_counts = (filtered_genres.groupby("genre_name")["movie_id"].nunique()
                    .reset_index(name="movie_count").sort_values("movie_count", ascending=False))
    if not genre_counts.empty:
        right.plotly_chart(
            px.pie(genre_counts, names="genre_name", values="movie_count", hole=0.45,
                   title="Genre distribution in filtered selection"),
            use_container_width=True
        )
    else:
        right.info("No genre records match the current filters.")

    st.subheader("Budget vs revenue")
    financial = filtered[(filtered["budget"] > 0) & (filtered["revenue"] > 0)].copy()
    if not financial.empty:
        st.plotly_chart(
            px.scatter(financial, x="budget", y="revenue", color="original_language",
                       size="vote_count", hover_name="title", hover_data=["release_year", "vote_average"],
                       title="Production budget vs box-office revenue",
                       labels={"budget": "Budget (USD)", "revenue": "Revenue (USD)"}),
            use_container_width=True
        )
    else:
        st.info("No movies with both positive budget and revenue match the current filters.")

    st.subheader("Insight from the current selection")
    if not filtered.empty:
        best_genre = genre_counts.iloc[0] if not genre_counts.empty else None
        best_movie = top_revenue.iloc[0] if not top_revenue.empty else None
        insight_parts = [f"The selection contains {filtered.movie_id.nunique():,} movies."]
        if best_genre is not None:
            insight_parts.append(f"{best_genre['genre_name']} is the most represented genre ({int(best_genre['movie_count'])} movies).")
        if best_movie is not None:
            insight_parts.append(f"The highest recorded revenue is for {best_movie['title']} ({money(best_movie['revenue'])}).")
        st.info(" ".join(insight_parts))
    else:
        st.info("No movies match the selected filters. Widen the year range or relax the other filters.")
    st.caption("Zero budget/revenue values are treated as unavailable for financial analysis. Revenue is as recorded in the supplied dataset.")

elif page == "Query Explorer":
    st.title("Query Explorer")
    st.write("Run any of the ten SQL analyses specified in the GUVI project document.")
    selected_query = st.selectbox("Select a saved SQL query", list(SQL_QUERIES.keys()), key="selected_sql_query")
    if st.button("Run query", type="primary", key="run_sql_query"):
        if filtered.empty:
            st.warning("No movies match the current filters. Adjust the shared filters before running a query.")
        else:
            sql_conn = make_filtered_sql_connection(filtered)
            try:
                result = pd.read_sql_query(SQL_QUERIES[selected_query], sql_conn)
                st.session_state["last_query_result"] = result
                st.session_state["last_query_name"] = selected_query
            except Exception as exc:
                st.error(f"Query failed: {exc}")
            finally:
                sql_conn.close()

    if "last_query_result" in st.session_state and st.session_state.get("last_query_name") == selected_query:
        result = st.session_state["last_query_result"]
        st.success(f"{len(result):,} rows returned for the current saved query.")
        st.dataframe(result, use_container_width=True, hide_index=True)
        st.download_button("Download query result", result.to_csv(index=False).encode("utf-8"),
                           "tmdb_query_result.csv", "text/csv")

        # Plot the first useful categorical/numeric pair when the result supports it.
        numeric_cols = result.select_dtypes(include="number").columns.tolist()
        categorical_cols = result.select_dtypes(include=["object", "string"]).columns.tolist()
        if numeric_cols and categorical_cols and not result.empty:
            x_col = numeric_cols[0]
            y_col = categorical_cols[0]
            chart_data = result.head(20).copy()
            st.plotly_chart(px.bar(chart_data, x=x_col, y=y_col, orientation="h",
                                   title=f"{x_col.replace('_', ' ').title()} by {y_col.replace('_', ' ').title()}"),
                            use_container_width=True)
        elif len(numeric_cols) >= 2 and not result.empty:
            st.plotly_chart(px.scatter(result, x=numeric_cols[0], y=numeric_cols[1],
                                       title=f"{numeric_cols[0]} vs {numeric_cols[1]}"),
                            use_container_width=True)
        elif categorical_cols and not result.empty:
            # For list-style results (for example actors and movie titles), chart the
            # frequency of the first descriptive field so every saved query has a chart.
            frequency = (result[categorical_cols[0]].fillna("Unknown")
                         .value_counts().head(20).rename_axis(categorical_cols[0])
                         .reset_index(name="record_count"))
            st.plotly_chart(px.bar(frequency, x="record_count", y=categorical_cols[0],
                                   orientation="h", title=f"Records by {categorical_cols[0].replace('_', ' ').title()}"),
                            use_container_width=True)
        else:
            st.caption("No chartable rows were returned for this query.")

        st.subheader("Query insight")
        if result.empty:
            st.info("The query returned no rows for the current filter selection.")
        elif numeric_cols:
            st.info(f"The query returned {len(result):,} rows. The result includes numeric measure(s): {', '.join(numeric_cols)}. Review the table and chart to compare the selected records.")
        else:
            st.info(f"The query returned {len(result):,} rows for the current filter selection.")
    else:
        st.info("Choose a query and select **Run query** to view its table, chart and insight.")

else:
    st.title("About Reel Insights")
    st.markdown("""
    **Reel Insights** is an end-to-end exploratory data analysis project focused on
    the global movie industry using a TMDB dataset.

    ### Project workflow
    1. Data cleaning and validation using Pandas.
    2. Relational storage and querying using SQLite.
    3. Exploratory analysis using Pandas.
    4. Interactive visualizations and exploration using Streamlit.

    ### Interpretation notes
    - Zero budget/revenue values are treated as unavailable for financial analysis.
    - ROI is a simplified calculation using revenue and production budget only; it excludes marketing and distribution costs.
    - Genre counts overlap because a movie can belong to multiple genres.
    - Popularity and vote count are descriptive dataset metrics, not causal measures.
    - Query Explorer uses the same shared movie filters as the Dashboard.
    """)
    st.subheader("Dataset tables")
    for name in TABLES:
        st.write(f"- `{name}` — {len(D[name]):,} rows")
