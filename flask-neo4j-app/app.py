from flask import Flask, request, jsonify
from neo4j import GraphDatabase
from flask_cors import CORS

# Initialize the Flask app
app = Flask(__name__)
CORS(app)

# Connect to Neo4j
class Neo4jConnection:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def query(self, query, parameters=None):
        with self.driver.session() as session:
            return session.run(query, parameters).data()

# Replace these with your Neo4j credentials
# neo4j_conn = Neo4jConnection(
#     uri="bolt://localhost:7687",
#     user="neo4j",
#     password=""
# )

# Neo4j Aura
neo4j_conn = Neo4jConnection(
    uri="neo4j+s://2f4d6707.databases.neo4j.io",
    user="neo4j",
    password="ozkwISVE3JulnPCIvq23n0H1Bu5KEMgXQIpLXxONq3g"
)

# API endpoint to get rankings
@app.route('/ranking', methods=['GET'])
def get_ranking():
    try:
        # Get leagueID and season from query parameters
        league_id = request.args.get('leagueID', type=int)
        season = request.args.get('season', type=str)

        if not league_id or not season:
            return jsonify({"error": "Both 'leagueID' and 'season' parameters are required."}), 400
        
        # Create a unique graph projection name based on leagueID and season
        graph_name = f"seasonLeagueGraph{league_id}{season.replace('/', '')}"

        # Check if the graph projection already exists
        check_query = f"""
        CALL gds.graph.exists('{graph_name}') YIELD exists
        """
        exists_result = neo4j_conn.query(check_query)
        graph_exists = exists_result[0]['exists'] if exists_result else False


        if not graph_exists:

            # Create graph projection for the specified season and league
            projection_query = f"""
            CALL gds.graph.project.cypher(
            '{graph_name}',
            'MATCH (t:Team)-[:beat]->()
            WHERE EXISTS {{
                MATCH (t)-[r:beat]->()
                WHERE r.season = "{season}" AND toInteger(r.leagueID) = {league_id}
            }}
            RETURN id(t) AS id',
            'MATCH (team1:Team)-[r:beat]->(team2:Team)
            WHERE r.season = "{season}" AND toInteger(r.leagueID) = {league_id}
            RETURN id(team1) AS source, id(team2) AS target, r.weight AS weight',
            {{ validateRelationships: false }}
            )
            """
            neo4j_conn.query(projection_query)

        # Run the PageRank algorithm
        pagerank_query = f"""
        CALL gds.pageRank.stream('{graph_name}')
        YIELD nodeId, score
        RETURN gds.util.asNode(nodeId).team_long_name AS Team, score
        ORDER BY score DESC;
        """
        results = neo4j_conn.query(pagerank_query)

        ranked_results = []
        for idx, result in enumerate(results, start=1):
            ranked_results.append({
                "Team": result["Team"],
                "score": result["score"],
                "rank": idx
            })

        return jsonify(ranked_results)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API endpoint to get leagues
@app.route('/leagues', methods=['GET'])
def get_leagues():
    query = "MATCH (l:League) RETURN l.id AS id, l.name AS name"
    leagues = neo4j_conn.query(query)
    return jsonify([{"id": league["id"], "name": league["name"]} for league in leagues])

# API endpoint to get seasons for a league
@app.route('/seasons', methods=['GET'])
def get_seasons():
    league_id = request.args.get('leagueID')
    if not league_id:
        return jsonify({"error": "Missing leagueID parameter"}), 400

    try:
        query = """
        MATCH ()-[r:beat]->()
        WHERE r.leagueID = $leagueID  // No conversion to integer; match as a string
        RETURN DISTINCT r.season AS season
        ORDER BY season
        """
        results = neo4j_conn.query(query, {"leagueID": league_id})  # Pass leagueID directly as a string
        return jsonify([record['season'] for record in results])

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# API endpoint to get head-to-head stats
@app.route('/head_to_head', methods=['GET'])
def get_head_to_head():
    team1_id = request.args.get('team1_id')
    team2_id = request.args.get('team2_id')
    league_id = request.args.get('leagueID')
    
    query = f"""
    MATCH (team1:Team {{team_api_id: {team1_id}}})-[r:beat]-(team2:Team {{team_api_id: {team2_id}}})
    WHERE toInteger(r.leagueID) = {league_id}
    RETURN team1.team_short_name AS team1, team2.team_short_name AS team2,
           COUNT(CASE WHEN r.winner = team1.team_short_name THEN 1 ELSE NULL END) AS team1_wins,
           COUNT(CASE WHEN r.winner = team2.team_short_name THEN 1 ELSE NULL END) AS team2_wins,
           COUNT(CASE WHEN r.winner = "tie" THEN 1 ELSE NULL END) AS ties
    """
    results = neo4j_conn.query(query, {
        "team1_id": team1_id,
        "team2_id": team2_id,
        "league_id": league_id
    })
    return jsonify(results[0] if results else {})

# API endpoint to get teams for a league
@app.route('/teams', methods=['GET'])
def get_teams():
    league_id = request.args.get('leagueID')
    if not league_id:
        return jsonify({"error": "Missing leagueID parameter"}), 400

    try:
        query = f"""
        MATCH (t:Team)-[:beat]->()
        WHERE EXISTS {{
            MATCH (t)-[r:beat]->()
            WHERE toInteger(r.leagueID) = {league_id}
        }}
        RETURN DISTINCT t.team_api_id AS id, t.team_long_name AS team_long_name, t.team_short_name AS team_short_name
        ORDER BY team_long_name
        """
        results = neo4j_conn.query(query, {"leagueID": league_id})  # Pass leagueID
        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API endpoint to get team trends for a league
@app.route('/team_trend', methods=['GET'])
def team_trend():
    try:
        # Get leagueID and teamID from query parameters
        league_id = request.args.get('leagueID', type=int)
        team_id = request.args.get('teamID', type=int)

        if not league_id or not team_id:
            return jsonify({"error": "Both 'leagueID' and 'teamID' parameters are required."}), 400

        # Neo4j query to fetch the seasonal trend for the team
        query = f"""
        MATCH (team:Team {{team_api_id: {team_id}}})
        WITH team.team_short_name AS team_short_name, team
        MATCH (team)-[r:beat]-()
        WHERE toInteger(r.leagueID) = {league_id}
        WITH r.season AS season,
            COUNT(CASE WHEN r.winner = team_short_name THEN 1 ELSE NULL END) AS wins,
            COUNT(CASE WHEN r.loser = team_short_name THEN 1 ELSE NULL END) AS losses,
            SUM(CASE
                WHEN r.winner = team_short_name THEN r.winner_goals
                WHEN r.loser = team_short_name THEN r.loser_goals
                ELSE 0 END) AS goals_for,
            SUM(CASE
                WHEN r.winner = team_short_name THEN r.loser_goals
                WHEN r.loser = team_short_name THEN r.winner_goals
                ELSE 0 END) AS goals_against
        RETURN season, wins, losses, goals_for, goals_against
        ORDER BY season
        """

        results = neo4j_conn.query(query, {"leagueID": league_id, "teamID": team_id})

        if not results:
            return jsonify({"message": "No data found for the specified team and league."}), 404

        formatted_results = [
            {
                "season": record["season"],
                "wins": record["wins"],
                "losses": record["losses"],
                "goals_for": record["goals_for"],
                "goals_against": record["goals_against"]
            }
            for record in results
        ]

        return jsonify(formatted_results)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# API endpoint to get stats for a match ID
@app.route('/match_stats', methods=['GET'])
def get_match_stats():
    match_id = request.args.get('matchID', type=int)
    if not match_id:
        return jsonify({"error": "Missing matchID parameter"}), 400

    query = f"""
    MATCH (team1:Team)-[r:beat]-(team2:Team)
    WHERE toInteger(r.match_id) = {match_id}
    RETURN r.winner AS winner, r.loser AS loser, 
           r.winner_goals AS winner_goals, 
           r.loser_goals AS loser_goals
    LIMIT 1
    """
    try:
        result = neo4j_conn.query(query)
        if result:
            return jsonify(result[0]), 200
        else:
            return jsonify({"error": "Match not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API endpoint to get all matches for a season in a league
@app.route('/matches', methods=['GET'])
def get_matches():
    league_id = request.args.get('leagueID')
    season = request.args.get('season')

    if not league_id or not season:
        return jsonify({"error": "Both 'leagueID' and 'season' parameters are required."}), 400

    query = f"""
    MATCH ()-[r:beat]-()
    WHERE toInteger(r.leagueID) = {league_id} AND r.season = '{season}'
    RETURN DISTINCT toInteger(r.match_id) AS match_id
    ORDER BY match_id
    """
    try:
        results = neo4j_conn.query(query)
        return jsonify([{"match_id": record["match_id"]} for record in results])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API endpoint to update stats for a match
@app.route('/update_match', methods=['PUT'])
def update_match():
    data = request.json

    match_id = data.get("matchID")
    winner = data.get("winner")
    loser = data.get("loser")
    winner_goals = data.get("winner_goals")
    loser_goals = data.get("loser_goals")
    league_id = data.get("leagueID")
    season = data.get("season")
    print([match_id, winner, loser, winner_goals, loser_goals, league_id, season])

    if match_id is None or winner is None or loser is None or winner_goals is None or loser_goals is None or league_id is None or season is None:
        return jsonify({"error": "All fields are required"}), 400

    # Delete the existing relationship
    delete_query = f"""
    MATCH ()-[r:beat]-()
    WHERE toInteger(r.match_id) = {match_id}
    DELETE r
    """
    try:
        neo4j_conn.query(delete_query)

        # Create the new relationship
        create_query = f"""
        MATCH (team1:Team {{team_short_name: '{winner}'}})
        MATCH (team2:Team {{team_short_name: '{loser}'}})
        CREATE (team2)-[newRel:beat {{
            match_id: {match_id},
            winner: '{winner}',
            loser: '{loser}',
            winner_goals: {winner_goals},
            loser_goals: {loser_goals},
            scoreDifferential: {winner_goals - loser_goals},
            season: '{season}',
            weight: {abs(winner_goals - loser_goals)},
            leagueID: '{league_id}'
        }}]->(team1)
        """
        neo4j_conn.query(create_query)
        return jsonify({"message": "Match updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# API endpoint to add a new match to a season in a league
@app.route('/add_match', methods=['PUT'])
def add_match():
    try:
        data = request.json
        match_id = data.get("matchID")
        winner = data.get("winner")
        loser = data.get("loser")
        winner_goals = data.get("winner_goals")
        loser_goals = data.get("loser_goals")
        league_id = data.get("leagueID")
        season = data.get("season")

        if match_id is None or winner is None or loser is None or winner_goals is None or loser_goals is None or league_id is None or season is None:
            return jsonify({"error": "All fields are required"}), 400

        # Create the new relationship
        create_query = f"""
        MATCH (team1:Team {{team_short_name: '{winner}'}})
        MATCH (team2:Team {{team_short_name: '{loser}'}})
        CREATE (team2)-[newRel:beat {{
            match_id: {match_id},
            winner: '{winner}',
            loser: '{loser}',
            winner_goals: {winner_goals},
            loser_goals: {loser_goals},
            scoreDifferential: {winner_goals - loser_goals},
            season: '{season}',
            weight: {abs(winner_goals - loser_goals)},
            leagueID: '{league_id}'
        }}]->(team1)
        """
        neo4j_conn.query(create_query)

        return jsonify({"message": "Match added successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API endpoint to delete a match from a season in a league
@app.route('/delete_match', methods=['DELETE'])
def delete_match():
    try:
        match_id = request.args.get("matchID")

        if not match_id:
            return jsonify({"error": "Match ID is required"}), 400

        delete_query = f"""
        MATCH ()-[r:beat]-()
        WHERE toInteger(r.match_id) = {match_id}
        DELETE r
        """
        print(delete_query)
        neo4j_conn.query(delete_query)
        return jsonify({"message": "Match deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
