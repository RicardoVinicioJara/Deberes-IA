from flask import Flask, render_template, request, jsonify, Response
from neo4j import GraphDatabase
from json import dumps
from pandas import DataFrame
import numpy as np
import os

app = Flask(__name__)

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "1004"), encrypted=False)
session = driver.session()
session.close


def inicio():
    with driver.session() as session:
        with session.begin_transaction() as tx:
            lista = tx.run("""MATCH (n) return n.name, n.latitude, n.longitude""")

    records = []
    for record in lista:
        records.append({"name": record["n.name"], "latitude": record["n.latitude"], "longitude": record["n.longitude"]})
    return records


def A(origen, destino):
    with driver.session() as session:
        with session.begin_transaction() as tx:
            lista = tx.run("""
        MATCH (start:Station {name: '""" + origen + """'}), (end:Station {name: '""" + destino + """'})
        CALL gds.alpha.shortestPath.astar.stream({
     nodeQuery: 'MATCH (p:Station) RETURN id(p) AS id',
     relationshipQuery: 'MATCH (p1:Station)-[r:CONNECTION]->(p2:Station) RETURN id(p1) AS source, id(p2) AS target, r.time AS weight',
     startNode: start,
     endNode: end,
     relationshipWeightProperty: 'weight',
     propertyKeyLat: 'latitude',
     propertyKeyLat: 'longitude'
    })YIELD nodeId, cost
    RETURN gds.util.asNode(nodeId).name AS Provincia, cost as Distancia
""")

    records = []
    for record in lista:
        records.append({"name": record["Provincia"], "costo": record["Distancia"]})
    return records

def Costo(origen, destino):
    with driver.session() as session:
        with session.begin_transaction() as tx:
            lista = tx.run("""
       MATCH (start:Station {name: '"""+origen+"""'}), (end:Station {name: '"""+destino+"""'})
    CALL gds.alpha.shortestPath.stream({
      nodeProjection: 'Station',
      relationshipProjection: {
        ROAD: {
          type: 'CONNECTION',
          properties: 'time',
          orientation: 'UNDIRECTED'
        }
      },
      startNode: start,
      endNode: end,
      relationshipWeightProperty: 'time'
    })
    YIELD nodeId, cost
    RETURN gds.util.asNode(nodeId).name AS Provincia, cost AS costo
""")
    records = []
    for record in lista:
        records.append({"name": record["Provincia"], "costo": record["costo"]})
    return records

def Profundi(origen, destino):
    with driver.session() as session:
        with session.begin_transaction() as tx:
            lista = tx.run("""
       MATCH (a:Station{name:'"""+origen+"""'}), (d:Station{name:'"""+destino+"""'})
    WITH id(a) AS startNode, [id(d)] AS targetNodes
    CALL gds.alpha.dfs.stream('Pais', {startNode: startNode, targetNodes: targetNodes})
    YIELD path
    UNWIND [ n in nodes(path) | n.name ] AS tags
    RETURN tags as Provincia
    ORDER BY tags DESC
""")
    records = []
    num = 0;
    for record in lista:
        num = num + 1
        records.append({"name": record["Provincia"], "costo": num})
    return records

def Amplitud(origen, numero):
    with driver.session() as session:
        with session.begin_transaction() as tx:
            lista = tx.run("""
       MATCH (a:Station{name:'"""+origen+"""'})
    WITH id(a) AS startNode
    CALL gds.alpha.bfs.stream('Pais', {startNode: startNode, maxDepth: """+numero+"""})
    YIELD path
    UNWIND [ n in nodes(path) | n.name] AS tags
    RETURN tags
    ORDER BY tags
""")

    records = []
    num = 0;
    for record in lista:
        num = num + 1
        records.append({"name": record["tags"], "costo": num})
    return records


@app.route('/')
def index():
    lista = inicio()
    return render_template("index.html", lista=lista)


@app.route('/Amplitud', methods=['POST'])
def ampli():
    or1 = request.form['or2']
    des = request.form['num']
    lista = Amplitud(or1, des)
    return render_template("index.html", lista = lista)

@app.route('/Costo', methods=['POST'])
def cost():
    or1 = request.form['or1']
    des = request.form['de1']
    lista = Costo(or1, des)
    return render_template("index.html", lista = lista)

@app.route('/Profundidad', methods=['POST'])
def Prof():
    or1 = request.form['or3']
    des = request.form['de3']
    lista = Profundi(or1, des)
    return render_template("index.html", lista = lista)

@app.route('/A', methods=['POST'])
def hola():
    destino = request.form['dest']
    print(destino)
    lista = A("Ecuador", destino)
    return render_template("index.html", lista = lista)


@app.route("/graph")
def get_graph():
    results = session.run("MATCH (m:Station)<-[:CONNECTION]-(a:Station) RETURN m.name as nodo, collect(a.name) as cast "
                          "LIMIT $limit", {"limit": request.args.get("limit", 100)})
    nodes = []
    rels = []
    i = 0
    for record in results:
        nodes.append({"title": record["nodo"], "label": "nodo"})
        target = i
        i += 1
        for name in record['cast']:
            actor = {"title": name, "label": "name"}
            try:
                source = nodes.index(actor)
            except ValueError:
                nodes.append(actor)
                source = i
                i += 1
            rels.append({"source": source, "target": target})
    return Response(dumps({"nodes": nodes, "links": rels}),
                    mimetype="application/json")


if __name__ == '__main__':
    app.debug = True
    app.run()
