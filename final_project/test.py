import pandas as pd
import requests
from urllib.request import urlopen
import json
import plotly.express as px


params = {
  "format": "json"
}

df = pd.DataFrame(requests.get("https://waterwatch.usgs.gov/webservices/realtime", params = params) .json()["sites"])


df["site_no"] = df["site_no"].astype("int")


county_lookup = pd.read_csv("county_lookup.csv").dropna()

county_lookup["county"] = county_lookup["county"].astype("int").astype("str")

prepend_zero = lambda s: "0" + s if len(s) == 4 else s
county_lookup["county"] = county_lookup["county"].apply(prepend_zero)


plot_df = pd.merge(county_lookup,df,on="site_no")

state_data   = pd.DataFrame(plot_df.groupby("state_nm")["percentile"].mean().round(0)).reset_index()
county_data = pd.DataFrame(plot_df.groupby(["county","state_nm"])["percentile"].mean().round(0)).reset_index()


with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
    county_geojson = json.load(response)


fig = px.choropleth(state_data,locations='state_nm', color='percentile',
                           color_continuous_scale="Viridis",
                           scope="usa",
                           #geojson = county_geojson
                           locationmode = "USA-states"
                          )
fig.show()
