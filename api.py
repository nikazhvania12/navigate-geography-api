from flask import Flask, jsonify, json, request, send_from_directory, session
import psycopg2
import os
from flask_cors import CORS


app = Flask(__name__)

with open("config.json") as data:
    jsonData = json.load(data) 
    dbData = jsonData["dbProperties"]
    appData = jsonData["app"]

FLAGS_FOLDER = os.path.join(os.getcwd(), 'Resources')

CORS(app, supports_credentials=True, origins=[appData['frontend_url'], appData['frontend_url_local']], methods=["GET", "POST", "OPTIONS", "PUT"])

app.secret_key = appData["app_key"]
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

def get_conn():
    return psycopg2.connect(
        dbname=dbData["dbName"],
        user=dbData["user"],
        password=dbData["password"],
        host=dbData["host"],
        port=dbData["port"]
    )



@app.route('/login', methods=['POST'])
def login():
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        data = request.get_json()

        email = data.get('email')
        password = data.get('password')

        if email == '' or password == '':
            return {'Error': 'Email and Password Must Not Be Empty'}, 400 

        query = 'SELECT * FROM public.get_user(%s, %s)'
        cur.execute(query, (email, password))
        user = cur.fetchone()

        if user is None:
            return {'Error': "User Does Not Exist"}, 400 
        
        session['USER_ID'] = user[0]

        user_dict = {
            'id': user[0],
            'email': user[1],
            'username': user[3],
            'can_edit': user[4]
        }
        return jsonify(user_dict)

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'Error': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()




@app.route('/logout', methods=["GET"])
def logout():
    session.pop('USER_ID', None)
    return '', 204 
    



@app.route('/currentUser', methods=["GET"])
def get_current_user():
    conn = None
    cur = None
    try:
        user_id = session.get('USER_ID')

        if user_id is None:
            return jsonify({'id': -1})
        
        conn = get_conn()
        cur = conn.cursor()
        query = 'SELECT * FROM public.get_current_user(%s::int)'


        cur.execute(query, (int(user_id),))
        user = cur.fetchone()

        if user is None:
            return jsonify({'id': -1})
        
        user_json = {
            'id': user[0],
            'email': user[1], 
            'username': user[2],
            'can_edit': user[3]
        }

        return jsonify(user_json)

    except Exception as e:
        if conn:
            conn.rollback()
            return jsonify({'id': -1})
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route('/countries/update', methods=['PUT'])
def update_country():
    conn = None
    cur = None
    try:
        response = get_current_user()

        user = response.get_json() 

        if user.get('id') == -1:
            return {'Error': 'No Administrator Logged in, Request is Unauthorized'}, 400
        
        
        if user.get('can_edit') == False:
            return {'Error': f"Administrator {user.get('username')} Does Not Have Permission to Modify Data"}, 400

        conn = get_conn()
        cur = conn.cursor()
        data = request.get_json()

        additional_info = data.get('additional_info')

        id = data.get('id')
        water_supply = data.get('water_supply')
        resources = data.get('resources')
        population = data.get('population')
        description = str(additional_info.get('description'))
        is3rdworld = additional_info.get('is3rdworld')
        key_fact = str(additional_info.get('key_fact'))

        if (water_supply == None or resources == None or population == None or description == '' 
            or description == None or is3rdworld == None or key_fact == '' or key_fact == None):
                return {'Error': 'Empty Strings / NULL Values Not Permitted'}, 400
        
        
        query = 'SELECT * FROM public.update_country(%s, %s, %s, %s, %s, %s, %s)'

        cur.execute(query, (water_supply, resources, population, description, is3rdworld, key_fact, id))

        conn.commit()

        return []

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'Error': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route('/countries/get', methods=['POST'])
def get_countries():
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        data = request.get_json()

        name = data.get('name') 

        if name == None:
            waterSupplyFrom = int(data.get('waterSupplyFrom'))
            resourcesFrom = int(data.get('resourcesFrom'))
            populationFrom = int(data.get('populationFrom'))

            waterSupplyTo = int(data.get('waterSupplyTo'))
            resourcesTo = int(data.get('resourcesTo'))
            populationTo = int(data.get('populationTo'))
            
            res = get_countries_by_filters(cur, waterSupplyFrom, resourcesFrom, 
                                            populationFrom, waterSupplyTo, resourcesTo, populationTo)
        else: 
            res = get_country_by_name(cur, name)

        conn.commit()

        if len(res) > 1 and res[1] == 400:
            return res
        
        return jsonify(res)
       
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'Error': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()




@app.route('/flags/<filename>')
def get_flag(filename):
    try:
        return send_from_directory(FLAGS_FOLDER, filename)
    except Exception as e:
        return jsonify({"Error", str(e)}), 400



def get_countries_by_filters(cur, waterSupplyFrom, resourcesFrom, 
                            populationFrom, waterSupplyTo, resourcesTo, populationTo):
    
    if waterSupplyFrom == None or waterSupplyTo == None or resourcesFrom == None or resourcesTo == None or populationFrom == None or populationTo == None:
       return {'Error': "Invalid Filter Request: Fitler Values are incorrectly provided"}, 400 
    
    if waterSupplyFrom > waterSupplyTo or resourcesFrom > resourcesTo or populationFrom > populationTo:
        return {'Error': "Invalid Filter Request: From Filters are High in Value than To Filters"}, 400 
    
    if waterSupplyFrom > 100 or waterSupplyTo > 100 or resourcesFrom > 100 or resourcesTo > 100 or populationFrom > 100 or populationTo > 100:
        return {'Error': "Invalid Filter Request: Filter Value Must Not Exceed 100"}, 400  

    cur.execute("SELECT * FROM get_countries_maximums()")

    maximums = cur.fetchall()

    waterSupplyFrom = int(maximums[1][2] / 100 * waterSupplyFrom)
    waterSupplyTo = int(maximums[1][2] / 100 * waterSupplyTo)

    populationFrom = int(maximums[0][4] / 100 * populationFrom)
    populationTo = int(maximums[0][4] / 100 * populationTo)

    query = "SELECT * FROM get_countries_filters  (%s, %s, %s, %s, %s, %s)"
    cur.execute(query, (waterSupplyFrom, resourcesFrom, populationFrom, waterSupplyTo, resourcesTo, populationTo))

    rows = cur.fetchall()

    if rows == None:
        return []


    result = [{'multi_search': True,'id': row[0], 'name': row[1]} for row in rows]
    return result



def get_country_by_name(cur, name):

    query = "SELECT * FROM get_country_by_name (%s)"
    cur.execute(query, (name,))

    rows = cur.fetchall()

    if not rows:
        return []

    result = [{'multi_search': False, 'id': row[0], 'name': row[1], 'water_supply': row[2], 
              'resources': row[3], 'population': row[4], 
              'additional_info': {'description': row[5], 
              "is3rdworld": row[6], 'key_fact': row[7], 'flag_path': (request.host_url.rstrip('/') + row[8]) }} for row in rows]

    return result


# if __name__ == '__main__':
#     app.run(debug=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))