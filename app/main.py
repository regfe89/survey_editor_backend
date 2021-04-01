from graphene import ObjectType, String, Field, Schema, List, Int
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.graphql import GraphQLApp
import json
import os
from sqlalchemy import create_engine

from check_args import check_args

DBPASSWORD = os.environ.get('DBPASSWORD')
DBUSER = os.environ.get('DBUSER')
DBHOST = '192.168.31.177'
DBNAME = 'forest_bd_work'

DATABASE_URL = 'postgresql://' + DBUSER + ':' + """DBPASSWORD""" +  '@192.168.31.177/forest_bd_work'

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

app.get("/save_survey_template/")
def save_survey_template():
    # print(survey_id)
    return 'd'

