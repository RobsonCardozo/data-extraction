import os
import requests
from flask import Flask, render_template, send_from_directory, redirect, url_for, request
from pymongo import MongoClient
import json
import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings


class WikipediaSpider(scrapy.Spider):
    name = "wikipedia"
    allowed_domains = ["en.wikipedia.org"]
    start_urls = ["https://en.wikipedia.org/wiki/Main_Page"]

    def __init__(self, query=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query = query
        self.records = []

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
                "inprop": "url"
            }
        ).json()

        page = next(iter(api_response["query"]["pages"].values()))
        url = page["fullurl"]

        record = {
            'title': title,
            'summary': summary,
            'url': url,
            'query': self.query
        }
        self.records.append(record)

    def closed(self, reason):
        filename = f"{self.query}.json"
        with open(os.path.join("data", filename), "w") as file:
            json.dump(self.records, file)


app = Flask(__name__)

# Flask app routes
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/')
def index():
    return render_template('index.html', results=[])


@app.route('/search')
def search():
    query = request.args.get('query')
    if not query:
        return redirect(url_for('index'))

    spider = WikipediaSpider(query=query)
    process = CrawlerProcess(get_project_settings())
    process.crawl(spider)
    process.start()

    # Retrieve the search results from the file saved by the spider
    filename = f"{query}.json"
    with open(os.path.join("data", filename), "r") as file:
        search_results = json.load(file)

    formatted_results = []
    for result in search_results:
        formatted_result = {
            'title': result['title'],
            'summary': result['summary'],
            'url': result['url']
        }
        formatted_results.append(formatted_result)

    return render_template('index.html', results=formatted_results)


if __name__ == '__main__':
    app.run(debug=True)
