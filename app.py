import os
import requests
import json

from flask import Flask, render_template, send_from_directory, redirect, url_for, request
from pymongo import MongoClient
from scrapy import Spider
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings


class WikipediaSpiderPipeline:
    def open_spider(self, spider):
        self.records = []

    def close_spider(self, spider):
        file_path = os.path.join(os.getcwd(), "data", f"{spider.query}.json")
        with open(file_path, "w") as f:
            json.dump(self.records, f)

    def process_item(self, item, spider):
        self.records.append(dict(item))
        return item


class WikipediaSpider(Spider):
    name = "wikipedia"
    allowed_domains = ["en.wikipedia.org"]

    def __init__(self, query=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query = query
        self.start_urls = [f"https://en.wikipedia.org/wiki/{query}"]

    custom_settings = {"ITEM_PIPELINES": {"WikipediaSpiderPipeline": 300}}

    def parse(self, response):
        title = response.css("h1#firstHeading::text").get().strip()
        summary = response.css("div#mw-content-text p::text").get().strip()

        # Consulta a API da Wikipedia para obter informações adicionais sobre o título
        api_response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "prop": "extracts|info",
                "titles": title,
                "exsentences": 2,
                "explaintext": True,
                "inprop": "url",
            },
        ).json()

        page = next(iter(api_response["query"]["pages"].values()))
        url = page["fullurl"]

        item = {"title": title, "summary": summary, "url": url, "query": self.query}
        yield item


app = Flask(__name__)

# Flask app routes
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search")
def search():
    query = request.args.get("query")
    if not query:
        return redirect(url_for("index"))

    # Executa o spider para buscar os dados
    process = CrawlerProcess(get_project_settings())
    spider = WikipediaSpider(query=query)
    process.crawl(spider)
    process.start()

    # Obtém os resultados do spider e salva no MongoDB
    client = MongoClient("mongodb://localhost:27017/")
    db = client["wikipedia"]
    collection = db["pages"]

    results = list(spider.records)
    collection.insert_many(results)

    # Redireciona para a página de resultados
    return redirect(url_for("show_results", query=query))


@app.route("/results")
def show_results():
    query = request.args.get("query")
    if not query:
        return redirect(url_for("index"))

    # Obtém os resultados do MongoDB
    client = MongoClient("mongodb://localhost:27017/")
    db = client["wikipedia"]
    collection = db["pages"]

    results = list(collection.find({"query": query}))

    return render_template("results.html", query=query, results=results)


if __name__ == "__main__":
    app.run(debug=True)
