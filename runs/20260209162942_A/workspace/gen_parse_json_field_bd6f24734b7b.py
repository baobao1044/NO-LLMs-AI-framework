import json
def parse_json_field(s, key):
    return json.loads(s).get(key)
