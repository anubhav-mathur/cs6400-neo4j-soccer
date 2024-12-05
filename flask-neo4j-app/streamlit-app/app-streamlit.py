import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go

# Backend Flask API URL
BASE_URL = "https://cs6400-neo4j-soccer.onrender.com"  # Change if Flask runs on another host/port

st.title("Soccer Data Viewer")

st.sidebar.title("Choose a Feature Category")

tab = st.sidebar.radio("Feature Category", ["Analysis Features", "Data Management"])

if tab == "Analysis Features":
    selected_feature = st.sidebar.radio(
        "Select Analysis Feature",
        ["Team Rankings Viewer", "Head-to-Head", "Team Trend Viewer"]
    )
elif tab == "Data Management":
    selected_feature = st.sidebar.radio(
        "Select Data Management Feature",
        ["Update Match", "Add Match"]
    )


# # Add Tabs
# tab = st.sidebar.radio("Choose a Feature", ["Team Rankings Viewer", "Head-to-Head", "Team Trend Viewer", "Update Match", "Add Match"])

if selected_feature == "Team Rankings Viewer":
    st.header("Team Rankings")
    leagues_response = requests.get(f"{BASE_URL}/leagues")
    if leagues_response.status_code == 200:
        leagues = leagues_response.json()
        selected_league_seasons = selected_league_seasons = st.sidebar.selectbox(
            "Select League",
            options=leagues,
            format_func=lambda league: league["name"],
        )
    else:
        st.error("Error fetching leagues from the backend.")

    if leagues_response.status_code == 200 and selected_league_seasons:
        
        league_id = selected_league_seasons["id"]
        league_name = selected_league_seasons["name"]
        seasons_response = requests.get(f"{BASE_URL}/seasons?leagueID={league_id}")
        if seasons_response.status_code == 200:
            seasons = seasons_response.json()
            selected_season = st.sidebar.selectbox("Select Season", seasons)
        else:
            st.error("Error fetching seasons for the selected league.")

    # Main Rankings Table
    if leagues_response.status_code == 200 and seasons_response.status_code == 200 and selected_season:
        rankings_response = requests.get(f"{BASE_URL}/ranking?leagueID={league_id}&season={selected_season}")
        if rankings_response.status_code == 200:
            rankings = rankings_response.json()
            st.subheader(f"Rankings for League {league_id} ({league_name}) - Season {selected_season}")
            st.table(rankings)
        else:
            st.error("Error fetching rankings for the selected filters.")

elif selected_feature == "Head-to-Head":
    st.header("Head-to-Head Team Comparison")

    # Fetch leagues
    leagues_response = requests.get(f"{BASE_URL}/leagues")
    if leagues_response.status_code == 200:
        leagues = leagues_response.json()
        selected_league = st.sidebar.selectbox(
            "Select League",
            options=leagues,
            format_func=lambda league: league["name"],  # Display only the name
        )
    else:
        st.error("Error fetching leagues from the backend.")

    # Fetch teams dynamically based on the selected league
    if leagues_response.status_code == 200 and selected_league:
        league_id = selected_league["id"]
        teams_response = requests.get(f"{BASE_URL}/teams?leagueID={league_id}")
        if teams_response.status_code == 200:
            teams = teams_response.json()
            # Dropdown for Team 1
            team1 = st.selectbox(
                "Select Team 1",
                teams,
                format_func=lambda x: x["team_long_name"]
            )

            # Filter the list for Team 2 to exclude the selected Team 1
            filtered_teams = [team for team in teams if team["id"] != team1["id"]]

            # Dropdown for Team 2
            team2 = st.selectbox(
                "Select Team 2",
                filtered_teams,
                format_func=lambda x: x["team_long_name"]
            )
        else:
            st.error("Error fetching teams for the selected league.")

        # Compare teams if both are selected
        if team1 and team2:
            response = requests.get(f"{BASE_URL}/head_to_head?team1_id={team1['id']}&team2_id={team2['id']}&leagueID={league_id}")
            if response.status_code == 200:
                stats = response.json()
                if not stats:
                    st.warning(f"No matches played between {team1['team_long_name']} and {team2['team_long_name']} yet.")
                else:
                    team1_name = team1['team_long_name']
                    team2_name = team2['team_long_name']

                    total_matches = stats['team1_wins'] + stats['team2_wins'] + stats['ties']

                    st.subheader(f"Head-to-Head: {team1_name} vs {team2_name}")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric(label=f"{team1_name} Wins", value=stats['team1_wins'])
                    with col2:
                        st.metric(label="Ties", value=stats['ties'])
                    with col3:
                        st.metric(label=f"{team2_name} Wins", value=stats['team2_wins'])

                    st.write(f"Total Matches Played: {total_matches}")
            else:
                st.error("Error fetching head-to-head comparison.")

elif selected_feature == "Team Trend Viewer":
    st.header("Team Performance Trend")

    # Fetch leagues
    leagues_response = requests.get(f"{BASE_URL}/leagues")
    if leagues_response.status_code == 200:
        leagues = leagues_response.json()
        selected_league = st.sidebar.selectbox(
            "Select League",
            options=leagues,
            format_func=lambda league: league["name"],  # Display only the name
        )
    else:
        st.error("Error fetching leagues from the backend.")

    # Fetch teams dynamically based on the selected league
    if leagues_response.status_code == 200 and selected_league:
        league_id = selected_league["id"]
        teams_response = requests.get(f"{BASE_URL}/teams?leagueID={league_id}")
        if teams_response.status_code == 200:
            teams = teams_response.json()
            selected_team = st.sidebar.selectbox(
                "Select Team",
                options=teams,
                format_func=lambda x: x["team_long_name"]
            )
        else:
            st.error("Error fetching teams for the selected league.")

    # Fetch and plot team trends
    if selected_team:
        team_id = selected_team["id"]
        trend_response = requests.get(f"{BASE_URL}/team_trend?leagueID={league_id}&teamID={team_id}")
        if trend_response.status_code == 200:
            trend_data = trend_response.json()

            trend_df = pd.DataFrame(trend_data)

            st.subheader(f"Performance Trends for {selected_team['team_long_name']}")

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=trend_df['season'], y=trend_df['wins'], 
                mode='lines+markers', name='Wins', line=dict(color='green')
            ))
            fig.add_trace(go.Scatter(
                x=trend_df['season'], y=trend_df['losses'], 
                mode='lines+markers', name='Losses', line=dict(color='red')
            ))
            fig.add_trace(go.Scatter(
                x=trend_df['season'], y=trend_df['goals_for'], 
                mode='lines+markers', name='Goals For', line=dict(color='blue')
            ))
            fig.add_trace(go.Scatter(
                x=trend_df['season'], y=trend_df['goals_against'], 
                mode='lines+markers', name='Goals Against', line=dict(color='orange')
            ))

            fig.update_layout(
                title=f"Performance Trends: {selected_team['team_long_name']}",
                xaxis_title="Season",
                yaxis_title="Count",
                legend_title="Metrics",
                template="plotly_white",
                xaxis=dict(tickangle=-45),
                hovermode="x unified"
            )

            st.plotly_chart(fig)
        else:
            st.error("Error fetching performance trends.")

elif selected_feature == "Update Match":
    st.header("Update Match Details")

    # Fetch leagues
    leagues_response = requests.get(f"{BASE_URL}/leagues")
    if leagues_response.status_code == 200:
        leagues = leagues_response.json()
        selected_league = st.sidebar.selectbox(
            "Select League",
            options=leagues,
            format_func=lambda league: league["name"],
        )
    else:
        st.error("Error fetching leagues from the backend.")

    if selected_league:
        league_id = selected_league["id"]

        # Fetch seasons for the league
        seasons_response = requests.get(f"{BASE_URL}/seasons?leagueID={league_id}")
        if seasons_response.status_code == 200:
            seasons = seasons_response.json()
            selected_season = st.sidebar.selectbox("Select Season", seasons)
        else:
            st.error("Error fetching seasons.")

        if selected_season:
            # Fetch match IDs for the league and season
            match_response = requests.get(f"{BASE_URL}/matches?leagueID={league_id}&season={selected_season}")
            if match_response.status_code == 200:
                matches = match_response.json()
                selected_match = st.sidebar.selectbox(
                    "Select Match ID",
                    matches,
                    format_func=lambda x: f"{x['match_id']}"
                )
            else:
                st.error("Error fetching matches.")

            if selected_match:
                match_id = selected_match["match_id"]

                # Fetch match stats for the selected match
                match_stats_response = requests.get(f"{BASE_URL}/match_stats?matchID={match_id}")
                if match_stats_response.status_code == 200:
                    match_stats = match_stats_response.json()

                    # Display current match stats
                    st.subheader("Current Match Details")
                    winner = st.text_input("Winner", match_stats["winner"], disabled=True)
                    loser = st.text_input("Loser", match_stats["loser"], disabled=True)
                    winner_goals = st.number_input("Winner Goals", value=match_stats["winner_goals"], min_value=0)
                    loser_goals = st.number_input("Loser Goals", value=match_stats["loser_goals"], min_value=0)

                    col1, col2 = st.columns(2)

                    # Update match details
                    with col1:
                        if st.button("Submit Updates"):
                            update_payload = {
                                "matchID": match_id,
                                "winner": winner,
                                "loser": loser,
                                "winner_goals": winner_goals,
                                "loser_goals": loser_goals,
                                "leagueID": league_id,
                                "season": selected_season
                            }
                            update_response = requests.put(f"{BASE_URL}/update_match", json=update_payload)
                            if update_response.status_code == 200:
                                st.success("Match details updated successfully.")
                            else:
                                st.error("Error updating match details.")
                    
                    with col2:
                        if st.button("Delete Match"):
                            delete_response = requests.delete(f"{BASE_URL}/delete_match?matchID={match_id}")
                            if delete_response.status_code == 200:
                                st.success("Match deleted successfully.")
                            else:
                                st.error(f"Error deleting match: {delete_response.json().get('error')}")
                else:
                    st.error("Error fetching match stats.")


elif selected_feature == "Add Match":
    st.header("Add Match")

    # Fetch leagues
    leagues_response = requests.get(f"{BASE_URL}/leagues")
    if leagues_response.status_code == 200:
        leagues = leagues_response.json()
        selected_league = st.selectbox(
            "Select League",
            options=leagues,
            format_func=lambda league: league["name"]
        )
    else:
        st.error("Error fetching leagues from the backend.")

    # Fetch seasons dynamically based on the selected league
    if leagues_response.status_code == 200 and selected_league:
        league_id = selected_league["id"]
        seasons_response = requests.get(f"{BASE_URL}/seasons?leagueID={league_id}")
        if seasons_response.status_code == 200:
            seasons = seasons_response.json()
            selected_season = st.selectbox("Select Season", seasons)
        else:
            st.error("Error fetching seasons for the selected league.")

    # Fetch teams dynamically based on the selected league and season
    if selected_season:
        teams_response = requests.get(f"{BASE_URL}/teams?leagueID={league_id}")
        if teams_response.status_code == 200:
            teams = teams_response.json()

            # Dropdown for Team 1
            team1 = st.selectbox(
                "Select Team 1 (Winner)",
                teams,
                format_func=lambda x: x["team_long_name"]
            )

            # Filter the list for Team 2 to exclude the selected Team 1
            filtered_teams = [team for team in teams if team["id"] != team1["id"]]

            # Dropdown for Team 2
            team2 = st.selectbox(
                "Select Team 2 (Loser)",
                filtered_teams,
                format_func=lambda x: x["team_long_name"]
            )
        else:
            st.error("Error fetching teams for the selected league.")

    # Add Match Details
    if team1 and team2:
        st.write("Enter Match Details")
        match_id = st.number_input("Match ID", min_value=1, step=1)
        winner_goals = st.number_input("Winner Goals", min_value=0, step=1)
        loser_goals = st.number_input("Loser Goals", min_value=0, step=1)

        if st.button("Add Match"):
            add_payload = {
                "matchID": match_id,
                "winner": team1["team_short_name"],
                "loser": team2["team_short_name"],
                "winner_goals": winner_goals,
                "loser_goals": loser_goals,
                "leagueID": league_id,
                "season": selected_season
            }
            add_response = requests.put(f"{BASE_URL}/add_match", json=add_payload)
            if add_response.status_code == 200:
                st.success("Match added successfully.")
            else:
                st.error(f"Error adding match: {add_response.json().get('error')}")


