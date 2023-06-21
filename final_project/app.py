# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

import json
from functools import reduce
from urllib.request import urlopen
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import requests
from dash import Dash, Input, Output, State, ctx, dcc, html
from dash_bootstrap_templates import load_figure_template

load_figure_template('lux')

params = {"format": "json"}

df = pd.DataFrame(
    requests.get("https://waterwatch.usgs.gov/webservices/realtime",
                 params=params).json()["sites"])

df["site_no"] = df["site_no"].astype("int64")

county_lookup = pd.read_csv("county_lookup.csv").dropna()

county_lookup["county_fips"] = county_lookup["county_fips"].astype(
    "int").astype("str")

prepend_zero = lambda s: "0" + s if len(s) == 4 else s
county_lookup["county_fips"] = county_lookup["county_fips"].apply(prepend_zero)

plot_df = pd.merge(county_lookup, df, on="site_no")

plot_df = plot_df[plot_df["percentile"] != 0].dropna()
plot_df = plot_df.rename(columns={'percentile': "realtime"})

df_list = []

for n in ["7", "14", "28"]:
    df = pd.DataFrame(
        requests.get(f"https://waterwatch.usgs.gov/webservices/flows{n}d",
                     params=params).json()["sites"]).dropna()
    df = df[df["percentile"] != 0]
    df["site_no"] = df["site_no"].astype("int64")
    df = df[["site_no", "percentile"]]
    df = df.rename(columns={'percentile': f'{n}'})
    df_list.append(df)

df_list.append(plot_df)

plot_df = reduce(lambda left, right: left.merge(right, on='site_no'), df_list)

state_data = plot_df.groupby(["state_nm", "state_code"
                              ])[["realtime", "7", "14",
                                  "28"]].median().round(2).reset_index()

county_data = plot_df.groupby([
    "state_nm", "county_nm", "county_fips", "state_code"
])[["realtime", "7", "14", "28"]].median().round(2).reset_index()

county_dict = dict(zip(county_data['county_fips'], county_data['county_nm']))
state_dict = dict(zip(county_data['state_code'], county_data['state_nm']))

with urlopen(
        'https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json'
) as response:
    county_geojson = json.load(response)

app = Dash(external_stylesheets=[dbc.themes.LUX])

SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "24rem",
    "padding": "2rem 1rem",
    "background-color": "#f8f9fa",
}

sidebar = html.Div([
    html.H2("Filters"),
    html.Hr(),
    dbc.Nav(
        [
            html.P("State Filter", className="lead"),
            dcc.Dropdown(state_data['state_nm'].unique(),
                         'State',
                         id='us-state-select',
                         multi=True,
                         placeholder="Select State"),
            html.Br(),
            html.P("County Filter", className="lead"),
            dcc.Dropdown(county_data['county_nm'].unique(),
                         'County',
                         id='county-select',
                         placeholder="Select County",
                         multi=True)
        ],
        vertical=True,
        pills=True,
    ),
],
                   style=SIDEBAR_STYLE)

app.layout = html.Div(children=[
    dbc.Row([
        dbc.Col(),
        dbc.Col(html.H1('US Realtime StreamFlow'),
                width=10,
                style={
                    'margin-top': '32px',
                    'textAlign': 'center'
                })
    ]),
    dbc.Row([
        dbc.Col(sidebar),
        dbc.Col(
            [dcc.Graph(
                id="map"), dcc.Graph(id='line-plot')],
            width=9,
            style={
                'margin-left': '5px',
                'margin-top': '7px',
                'margin-right': '5px'
            },
        )
    ])
])


@app.callback(Output('map', 'figure'), Output('line-plot', 'figure'),
              Input('us-state-select', 'value'), Input('county-select',
                                                       'value'))
def filter_map(selected_state, selected_county):

    if selected_state == "State":
        selected_state = []

    if selected_county == "County":
        selected_county = []

    if not selected_state and not selected_county:
        filtered_df = state_data
        locations = "state_code"
        geojson = None
        locationmode = "USA-states"
        fitbounds = False
        id_vars = ['state_nm', 'state_code']
        hover_name = "state_nm"
        title = "State"
    else:
        if not selected_state:
            state_filter = [True] * len(county_data)
        else:
            state_filter = county_data['state_nm'].isin(selected_state)
        if not selected_county:
            county_filter = [True] * len(county_data)
        else:
            county_filter = county_data['county_nm'].isin(selected_county)

        filtered_df = county_data[state_filter & county_filter]
        locations = "county_fips"
        geojson = county_geojson
        locationmode = None
        fitbounds = True
        id_vars = ['state_nm', 'county_nm', 'county_fips', 'state_code']
        hover_name = "county_nm"
        title = "County"

    map_fig = px.choropleth(filtered_df,
                            locations=locations,
                            color='realtime',
                            scope="usa",
                            color_continuous_scale='Spectral',
                            geojson=geojson,
                            locationmode=locationmode,
                            hover_name=hover_name,
                            range_color=[0, 100])

    if fitbounds:
        map_fig.update_geos(fitbounds="locations")

    map_fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
    map_fig.update_layout(coloraxis_colorbar_title_text='Percentile')

    line_plot_data = filtered_df.melt(id_vars=id_vars,
                                      var_name='n',
                                      value_name='percentile')

    line_fig = px.line(line_plot_data,
                       x='n',
                       y='percentile',
                       color=hover_name,
                       line_group="state_nm",
                       hover_name=hover_name)

    line_fig.update_xaxes(categoryorder='array',
                          categoryarray=["28", "14", "7", "realtime"])

    line_fig.update_layout(yaxis_title="Percentile")

    line_fig.update_layout(legend_title_text=title)

    return map_fig, line_fig


@app.callback(Output('county-select', 'options'),
              Input('us-state-select', 'value'))
def set_county_options(selected_state):

    if selected_state == "State":
        selected_state = []

    if not selected_state:
        county_options = county_data["county_nm"].unique()
    else:
        county_options = county_data[county_data["state_nm"].isin(
            selected_state)]["county_nm"].unique()

    return county_options


@app.callback(Output('us-state-select', 'options'),
              Input('county-select', 'value'))
def set_state_options(selected_county):

    if not selected_county or selected_county == "County":
        state_options = county_data["state_nm"].unique()
    else:
        state_options = county_data[county_data["county_nm"].isin(
            selected_county)]["state_nm"].unique()

    return state_options


if __name__ == '__main__':
    app.run_server(debug=True)
