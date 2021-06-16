from graphene import ObjectType, String, Field, Schema, List, Int
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.graphql import GraphQLApp
import json
import os
import urllib.request
from sqlalchemy import create_engine
from fastapi.encoders import jsonable_encoder
import base64
import requests

from check_args import check_args

DBPASSWORD = os.environ.get('DBPASSWORD')
DBUSER = os.environ.get('DBUSER')
DBHOST = '192.168.31.177'
DBNAME = 'forestry_bd'

DATABASE_URL = 'postgresql://' + DBUSER + ':' + DBPASSWORD +  '@192.168.31.177/forest_bd_work'

db = create_engine(DATABASE_URL)


class Stand(ObjectType):
    stand_code = Int()
    stand_id = Int()

class Block(ObjectType):
    block_num = Int()
    block_id = Int()
    stand_list = List(Stand)

    def resolve_stand_list(self, info):
        results = db.execute("""SELECT stand_code, gid FROM forest.stand WHERE block_id={}""".format(
            self.block_id))
        resp = []
        for stand in results:
            resp.append(
                Stand(stand_code=stand[0], stand_id=stand[1]))
        return resp


class Forestry(ObjectType):
    forestry_ru = String()
    forestry_en = String()
    forestry_id = Int()
    block_list = List(Block)

    def resolve_block_list(self, info):
        results = db.execute("""SELECT block_num, gid FROM forest.block WHERE forestry_id={}""".format(
            self.forestry_id))
        resp = []
        for block in results:
            resp.append(
                Block(block_num=block[0], block_id=block[1]))
        return resp


class Leshoz(ObjectType):
    leshoz_ru = String()
    leshoz_en = String()
    leshoz_id = Int()
    forestry_list = List(Forestry)

    def resolve_forestry_list(self, info):
        results = db.execute("""SELECT forestry_ru, forestry_en, gid FROM forest.forestry WHERE leshoz_id={}""".format(
            self.leshoz_id))
        resp = []
        for forestry in results:
            resp.append(
                Forestry(forestry_ru=forestry[0], forestry_en=forestry[1], forestry_id=forestry[2]))
        return resp


class Oblast(ObjectType):
    oblast_ru = String()
    oblast_en = String()
    oblast_id = Int()
    leshoz_list = List(Leshoz)

    def resolve_leshoz_list(self, info):
        results = db.execute("""SELECT leshoz_ru, leshoz_en, leshoz_id FROM forest.leshoz WHERE oblast_id={}""".format(
            self.oblast_id))
        resp = []
        for leshoz in results:
            resp.append(
                Leshoz(leshoz_ru=leshoz[0], leshoz_en=leshoz[1], leshoz_id=leshoz[2]))
        return resp


class Select(ObjectType):
    id = Int()
    name = String()

class Query(ObjectType):
    oblast_list = List(Oblast)
    select_list = List(Select, table_name=String(), name_column=String(), id_column=String(), where_clause=String())

    def resolve_select_list(self, info, table_name, name_column, id_column, where_clause=''):
        resp = []
        args = [table_name, name_column, id_column]
        if check_args(args) == 'not valid':
            return
        query = "SELECT " + id_column + ", " + name_column + " FROM forest." + table_name + " " + where_clause
        # query = query.replace(',,', ',')
        # query = query.replace(', FROM', ' FROM')
        results = db.execute(query)
        for row in results:
            resp.append(Select(id=row[0], name=row[1]))
        return resp

    def resolve_oblast_list(self, info):
        results = db.execute("SELECT oblast_ru, oblast_en, oblast_id FROM topo.oblast")
        resp = []
        for oblast in results:
            resp.append(
                Oblast(oblast_ru=oblast[0], oblast_en=oblast[1], oblast_id=oblast[2]))
        return resp


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_route("/", GraphQLApp(schema=Schema(query=Query)))

@app.post("/save_survey_template")
async def save_survey_template(request: Request, id:  str = ""):
    data = await request.json()
    survey_id = data['survey_id']
    name = data['name']
    data = json.dumps(data)
    ids = db.execute("SELECT survey_id FROM mobile.templates")
    for id_num in ids:
        if id == id_num[0]:
            query = db.execute("UPDATE mobile.templates SET (survey_body, survey_name) = ('{}', '{}') WHERE survey_id = '{}'".format(data, name, id))
            return 'success'
    query = db.execute("INSERT INTO mobile.templates (survey_id, survey_name, survey_body) VALUES ('{}', '{}', '{}')".format(survey_id, name, data))
    return 'success'


@app.get("/get_templates_list")
def get_templates_list():
    templates_list = db.execute("SELECT survey_id, survey_name FROM mobile.templates")
    a_list = []
    for template in templates_list:
        a_list.append(jsonable_encoder(template))
    response = json.dumps(a_list)
    return response

@app.get("/get_template_by_id")
def get_template_by_id(id: str):
    results = db.execute("SELECT survey_body as survey FROM mobile.templates WHERE survey_id ='{}'".format(id))
    response = None
    for template in results:
        response = jsonable_encoder(template)
    return json.dumps(response)

@app.get("/generate_objects")
def generate_objects(id: str, values: str):
    values = json.loads(values)
    ids = []
    for value in values:
        ids.append(value['value'])
    query_text = db.execute("SELECT survey_body -> 'objects_query_text' as query_text FROM mobile.templates WHERE survey_id ='{}'".format(id))
    for query in query_text:
        query_text = jsonable_encoder(query)['query_text']
    query_text = query_text.format(*ids)
    stand_list = db.execute(query_text)
    # results = db.execute("SELECT survey_body as survey FROM mobile.templates WHERE survey_id ='{}'".format(id))
    response = None
    result = []
    for template in stand_list:
        response = jsonable_encoder(template)
        result.append(response)
    return json.dumps(result)

@app.get("/generate_mbtiles")
def generate_mbtiles(id: str, values: str):
    values = json.loads(values)
    ids = []
    for value in values:
        ids.append(value['value'])
    # geom_field_query = db.execute("SELECT survey_body -> 'geom_field' as geom_field FROM mobile.templates WHERE survey_id ='{}'".format(id))
    # query_text = db.execute("SELECT survey_body -> 'bounds_query_text' as initial_fields, survey_body -> 'geom_field' as geom_field, survey_body -> 'object_code' as object_code FROM mobile.templates WHERE survey_id ='{}'".format(id))
    query_text = db.execute("SELECT survey_body -> 'bounds_query_text' as query_text FROM mobile.templates WHERE survey_id ='{}'".format(id))
    for query in query_text:
        query_text = jsonable_encoder(query)['query_text']
        # geom_field = jsonable_encoder(query)['geom_field']
        # obj_field = jsonable_encoder(query)['object_code']
    query_text = query_text.format(*ids)
    # query_text = query_text.replace(geom_field, "ST_XMin(ST_Extent({0})), ST_XMax(ST_Extent({0})), ST_YMin(ST_Extent({0})), ST_YMax(ST_Extent({0}))".format(geom_field))
    # query_text = query_text.replace('ST_AsGeoJSON', '')
    # query_text = query_text.replace(obj_field, "")
    # query_text = query_text.replace(',  FROM', 'FROM')
    extent = db.execute(query_text)
    response = None
    print('1st', extent)
    for item in extent:
        response = (jsonable_encoder(item))
        result = response
    padding = 0.003
    # result = result.strip(')(').split(',')
    print('resutl', result)
    top = float(result['st_ymax']) + padding
    bottom = float(result['st_ymin']) - padding
    left = float(result['st_xmin']) - padding
    right = float(result['st_xmax']) + padding
    url = 'https://dev.forest.caiag.kg/mbtiles-generator/mbtiles?left=' + str(left) + '&bottom=' + str(bottom) + '&right=' + str(right) + '&top=' + str(top)
    print('url', url)
    urllib.request.urlretrieve(url, 'map.mbtiles')
    # https://dev.forest.caiag.kg/mbtiles-generator/mbtiles?left=72.7560069866762&bottom=41.3816081636863&right=72.7878707934176&top=41.417875180932
    # return json.dumps(result)
    return FileResponse('map.mbtiles', media_type="application/x-sqlite3")

@app.get("/generate_survey")
def generate_survey(id: str, values: str):
    query = db.execute("SELECT survey_body FROM mobile.templates WHERE survey_id ='{}'".format(id))
    for elem in query:
        result = jsonable_encoder(elem)
    for elem in result['survey_body']['survey_body']:
        if elem['type'] == 'select':
            name = elem['select']['name_column']
            code = elem['select']['id_column']
            table = elem['select']['table_name']
            where_clause = elem['select']['where_clause']
            query_text = 'SELECT ' + name + ' ' + 'AS name, ' + code + ' ' + 'AS code ' + 'FROM ' + table + ' ' + where_clause
            results = db.execute(query_text)
            response = None
            result2 = []
            for value in results:
                response = jsonable_encoder(value)
                result2.append(response)
            elem['select_values'] = result2
        elif elem['type'] == 'table':
            for table_elem in elem['fields'][0]:
                if table_elem['type'] == 'select':
                    name = table_elem['select']['name_column']
                    code = table_elem['select']['id_column']
                    table = table_elem['select']['table_name']
                    where_clause = table_elem['select']['where_clause']
                    query_text = 'SELECT ' + name + ' ' + 'AS name, ' + code + ' ' + 'AS code ' + 'FROM ' + table + ' ' + where_clause
                    results = db.execute(query_text)
                    response = None
                    result2 = []
                    for value in results:
                        response = jsonable_encoder(value)
                        result2.append(response)
                    table_elem['select_values'] = result2

    values = json.loads(values)
    ids = []
    for value in values:
        ids.append(value['value'])
    bounds_query_text = db.execute("SELECT survey_body -> 'bounds_query_text' as query_text FROM mobile.templates WHERE survey_id ='{}'".format(id))
    for query in bounds_query_text:
        bounds_query_text = jsonable_encoder(query)['query_text']
    #     geom_field = jsonable_encoder(query)['geom_field']
    #     obj_field = jsonable_encoder(query)['object_code']
    bounds_query_text = bounds_query_text.format(*ids)
    # orig_query = geom_query_text
    # geom_query_text = geom_query_text.replace(geom_field, "ST_Centroid(ST_Extent(the_geom))")
    # geom_query_text = geom_query_text.replace(obj_field, "")
    # geom_query_text = geom_query_text.replace(',  FROM', 'FROM')
    # center = db.execute(geom_query_text)
    # response = None
    # geom_result = ''
    # for item in center:
    #     response = jsonable_encoder(item)
    #     geom_result = response
    # extent_query = orig_query
    # extent_query = extent_query.replace(obj_field, "")
    # extent_query = extent_query.replace(',  FROM', 'FROM')
    # extent_query = extent_query.replace('ST_AsGeoJSON', "")
    # extent_query = extent_query.replace(geom_field, "ST_XMin(ST_Extent({0})), ST_XMax(ST_Extent({0})), ST_YMin(ST_Extent({0})), ST_YMax(ST_Extent({0}))".format(geom_field))
    # extent = db.execute(bounds_query_text)
    # response = None
    # extent_result = ''

    # extent_result = extent_result['row']
    # for item in extent_result:
    #     response = (jsonable_encoder(item)['row'])
    #     result = response
    # padding = 0.003
    extent = db.execute(bounds_query_text)
    response = None
    for item in extent:
        response = jsonable_encoder(item)
        extent_result = response
    print('2nd', extent)
    for item in extent:
        response = (jsonable_encoder(item))
        extent_result = response
    print('result', extent_result)
    # extent_result = result.strip(')(').split(',')
    # for item in extent_result:
    #     print('item', item)
        # item = float(item)
    # top = geom_result['st_ymax']
    # bottom = geom_result['st_ymin']
    # left = geom_result['st_xmin']
    # right = geom_result['st_xmax']
    # vert_center = (top + bottom)/2
    # horiz_center = (left + right)/2
    # print(vert_center, horiz_center)
    # return 's'
    # response = None
    # result3 = []
    # for template in stand_list:
    #     response = jsonable_encoder(template)
    #     result.append(response)
    # return 's'
    result['initial_fields'] = values
    result['bounds'] = extent_result
    print(result['bounds'])
    # result['center'] = json.loads(geom_result['st_asgeojson'])['coordinates']
    return json.dumps(result)

@app.get("/get_initial_fields")
def get_initial_fields(id: str):
    results = db.execute("SELECT survey_body -> 'initial_fields' as initial_fields FROM mobile.templates WHERE survey_id ='{}'".format(id))
    response = None
    for template in results:
        response = jsonable_encoder(template)
    return json.dumps(response)


@app.get("/send_standestimation_data")
def send_standestimation_data(data: str):
    data = json.loads(data)
    for item in data:
        if item['id'] == 'Номер лесхоза':
            item['id'] =  'leshoz_id'
            leshoz_id = item['val']
        elif item['id'] == 'Номер лесничества':
            forestry_num = item['val']
            item['id'] = 'forestry_num'
        elif item['id'] == 'Номер квартала':
            item['id'] = 'block_num'
            block_num = item['val']
        elif item['id'] == 'exposition_id':
            exposition_val = item['val']
    print(leshoz_id, forestry_num, block_num)
    forestry_id = get_forestry_id(leshoz_id, forestry_num)
    block_id = get_block_id(forestry_id, block_num)
    oblast_id = get_oblast_id(leshoz_id)
    exposition_id = get_expostition_id(exposition_val)
    print(forestry_id, block_id)
    data.append({'id': 'forestry_id', 'val': str(forestry_id)})
    data.append({'id': 'block_id', 'val': str(block_id)})
    data.append({'id': 'oblast_id', 'val': str(oblast_id)})
    data.append({'id': 'oblast_id', 'val': str(oblast_id)})
    data.append({'id': 'unprocessed_flag', 'val': 1})
    data.append({'id': 'standestimation_cycle', 'val': '2'})
    for item in data:
        if item['id'] == 'exposition_id':
            item['val'] = str(exposition_id)
    # for item in data:
    #     print(item)
    # f = open('payload.json',)
    # data = json.load(f)
    data_bytes = json.dumps(data).encode("ascii")
    # Opening JSON file
    # f = open('payload.json',)
    # data = json.load(f)
    # print(data_bytes)
    # data64 = base64.b64encode(data_bytes)
    # data64 = data64.decode('ascii')
    # post_data = {}
    # post_data['base64'] = data64
    # post_data = json.dumps(post_data)
    # print(post_data)
    url = 'https://dev.forest.caiag.kg/ru/rent/standest/savestandestform'
    # post = urllib.request.urlopen(url, data=bytes(post_data), encoding="ascii")

    post_data = urllib.parse.urlencode({'base64': base64.b64encode(data_bytes)})
    post_data = post_data.encode('ascii')
    print(post_data)
    user_agent = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
    headers = { 'User-Agent' : user_agent,
            'Content-type': "application/x-www-form-urlencoded",
            'Accept': "text/plain"}
    request = urllib.request.Request(url, data=post_data, headers=headers)
    cookies = """show_red_items=1; _ga=GA1.2.631020320.1617350960; _ym_uid=161735096089548495; _ym_d=1617350960; _identity-frontend=a70afbde4814fde870f8fc974326e10c5ed40718117659e178080a4a3e2c4e7fa%3A2%3A%7Bi%3A0%3Bs%3A18%3A%22_identity-frontend%22%3Bi%3A1%3Bs%3A47%3A%22%5B76%2C%22yfPlk9L4YADp1bagnvrodpC1NIEucZ-w%22%2C2592000%5D%22%3B%7D; _csrf=dc45c1e918cb2b184c4082fe66deda44fc940e142446f74eae526b4c36c8fe13a%3A2%3A%7Bi%3A0%3Bs%3A5%3A%22_csrf%22%3Bi%3A1%3Bs%3A32%3A%22v00ig2tViiRAyYum94QXHo1nOS3Tgw-5%22%3B%7D; advanced-frontend=vepbsmkhen05f9rvcq71rkv6a0"""
    cookies={'show_red_items':1, '_ga':'GA1.2.631020320.1617350960', '_ym_uid':161735096089548495, '_ym_d':1617350960, '_identity-frontend':'a70afbde4814fde870f8fc974326e10c5ed40718117659e178080a4a3e2c4e7fa%3A2%3A%7Bi%3A0%3Bs%3A18%3A%22_identity-frontend%22%3Bi%3A1%3Bs%3A47%3A%22%5B76%2C%22yfPlk9L4YADp1bagnvrodpC1NIEucZ-w%22%2C2592000%5D%22%3B%7D', '_csrf':'dc45c1e918cb2b184c4082fe66deda44fc940e142446f74eae526b4c36c8fe13a%3A2%3A%7Bi%3A0%3Bs%3A5%3A%22_csrf%22%3Bi%3A1%3Bs%3A32%3A%22v00ig2tViiRAyYum94QXHo1nOS3Tgw-5%22%3B%7D', 'advanced-frontend':'vepbsmkhen05f9rvcq71rkv6a0'}
    response = requests.post(url, cookies={'_csrf': 'dc45c1e918cb2b184c4082fe66deda44fc940e142446f74eae526b4c36c8fe13a%3A2%3A%7Bi%3A0%3Bs%3A5%3A%22_csrf%22%3Bi%3A1%3Bs%3A32%3A%22v00ig2tViiRAyYum94QXHo1nOS3Tgw-5%22%3B%7D';'_identity-frontend':"""a70afbde4814fde870f8fc974326e10c5ed40718117659e178080a4a3e2c4e7fa%3A2%3A%7Bi%3A0%3Bs%3A18%3A%22_identity-frontend%22%3Bi%3A1%3Bs%3A47%3A%22%5B76%2C%22yfPlk9L4YADp1bagnvrodpC1NIEucZ-w%22%2C2592000%5D%22%3B%7D"""}, headers=headers).text
    print(request)
    # response = urllib.request.urlopen(request).read()
    print(response)
    # results = db.execute("SELECT survey_body -> 'initial_fields' as initial_fields FROM mobile.templates WHERE survey_id ='{}'".format(id))
    # response = None
    # for template in results:
    #     response = jsonable_encoder(template)
    return 's'
    return json.dumps(response)


def get_forestry_id(leshoz_id, forestry_num):
    result = db.execute("select gid from forest.forestry f where leshoz_id = '{}' and forestry_num = '{}'".format(leshoz_id, forestry_num))
    response = None
    for data in result:
        response = jsonable_encoder(data)
    return response['gid']

def get_block_id(forestry_id, block_num):
    result = db.execute("select gid from forest.block b where forestry_id = '{}' and block_num = '{}'".format(forestry_id, block_num))
    response = None
    for data in result:
        response = jsonable_encoder(data)
    return response['gid']

def get_oblast_id(leshoz_id):
    result = db.execute("select oblast_id from forest.leshoz l where leshoz_id = '{}'".format(leshoz_id))
    response = None
    for data in result:
        response = jsonable_encoder(data)
    return response['oblast_id']

def get_expostition_id(exposition_val):
    result = db.execute("select exposition_id from forest.exposition e where abbreviation = '{}'".format(exposition_val))
    response = None
    for data in result:
        response = jsonable_encoder(data)
    return response['exposition_id']
