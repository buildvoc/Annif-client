#!/usr/bin/env python3

import cgi
import json
import sys

import mysql.connector

print("Content-Type: text/plain; charset=utf-8")
print()

form = cgi.FieldStorage()

if "topics" not in form:
    topics = ["should"]
else:
    topics = form.getfirst("topics", "[]")
    topics = json.loads(topics)
    if not topics:
        print("error")
        sys.exit(1)
try:
    with mysql.connector.connect(user="root", password="", database="public") as db:
        with db.cursor(buffered=True) as cursor:
            select = "SELECT eprintid, id_number, edition, number, title, abstract FROM eprint "
            where = "WHERE eprint_status='archive' AND "
            for idx, topic in enumerate(topics):
                if idx != len(topics) - 1:
                    where += f"keywords LIKE '%{topic}%' AND "
                else:
                    where += f"keywords LIKE '%{topic}%' "
            order = "ORDER BY keywords DESC;"
            cursor.execute(select + where + order)
            results = {}
            for (eprintid, id_number, edition, number, title, abstract) in cursor:
                id_number = id_number.decode() if isinstance(id_number, bytes) else id_number
                edition = edition.decode() if isinstance(edition, bytes) else edition
                number = number.decode() if isinstance(number, bytes) else number
                title = title.decode() if isinstance(title, bytes) else title
                abstract = abstract.decode() if isinstance(abstract, bytes) else abstract
                results[eprintid] = [eprintid, id_number, edition, number, title, abstract]
            eprintids = results.keys()
            if eprintids:
                eprintids = "(" + ",".join(map(str, eprintids)) + ")"
                select = "SELECT eprintid, pos, main FROM document "
                where = f"WHERE eprintid IN {eprintids} AND placement=1 AND format='image' AND security='public';"
                cursor.execute(select + where)
                for (eprintid, pos, main) in cursor:
                    results[eprintid].append(main.decode() if isinstance(main, bytes) else main)
                    results[eprintid].append(pos.decode() if isinstance(pos, bytes) else pos)
            results = json.dumps(results)
            print(results)
            print()
except Exception as e:
    print("error")
    print(str(e))
