import lightningchart as lc
from obspy.clients.seedlink.easyseedlink import EasySeedLinkClient
from obspy import Stream
import threading
import time

# Set LightningChart license
lc.set_license("LICENSE_KEY")

# Create a dashboard with 1 column and 4 rows, using a Dark theme
dashboard = lc.Dashboard(columns=1, rows=4, theme=lc.Themes.Dark)
dashboard.open(live=True)

# Create a chart occupying the first three rows of the dashboard
chart = dashboard.ChartXY(column_index=0, row_index=0,
                          column_span=1, row_span=3)

chart.set_title('Seismic data from Trieste, Italy')

# Disposing default axes
chart.get_default_x_axis().dispose()
chart.get_default_y_axis().dispose()

# List to store series for each data stream
series_list = []

# High-Precision X-axis
x_axis = chart.add_x_axis(axis_type='linear-highPrecision')
x_axis.set_tick_strategy('DateTime')
x_axis.set_scroll_strategy('progressive')
x_axis.set_interval(start=0, end=10000, stop_axis_after=False)

# Function to add a series and corresponding Y-axis to the chart


def add_series_and_y_axis(chart, stack_index, title):
    y_axis = chart.add_y_axis(stack_index=stack_index)
    y_axis.set_margins(15 if stack_index > 0 else 0,
                       15 if stack_index < 2 else 0)
    y_axis.set_title(title)

    series = chart.add_line_series(
        x_axis=x_axis, y_axis=y_axis, data_pattern='ProgressiveX').set_line_thickness(2)
    series_list.append(series)
    return series


# Information for each data stream
titles = ["East-West", "North-South", "Vertical"]
channels = ["HHE", "HHN", "HHZ"]

# Add series and Y-axes to the chart for each data stream
for i in range(3):
    add_series_and_y_axis(chart, i, titles[i])

# Create Zoom Band Chart attached to the main ChartXY
zbc = dashboard.ZoomBandChart(chart=chart, column_index=0,
                              row_index=3, row_span=1, axis_type='linear-highPrecision')

# Add all series to the Zoom Band Chart
for series in series_list:
    zbc.add_series(series)

# DataBuffer class to manage incoming data


class DataBuffer():
    def __init__(self, client_count):
        self.data = []
        self.sleep_amount = 0.01
        for i in range(client_count):
            self.data.append({"name": i, "xs": [], "ys": []})

    def receive_data(self, client_data, client_name):
        xs, ys = client_data
        for client in self.data:
            if client['name'] == client_name:
                client['xs'].extend(xs)
                client['ys'].extend(ys)

    def add_data_to_series(self):
        # Checks if all clients have at least one data point
        if all(client['xs'] and client['ys'] for client in self.data):
            xs_combined = [client['xs'].pop(0) for client in self.data]
            ys_combined = [client['ys'].pop(0) for client in self.data]

            for i, series in enumerate(series_list):
                series.add([xs_combined[i]], [ys_combined[i]])

        total_data_points = sum(
            len(client_data['ys']) for client_data in self.data)

        if total_data_points > 1000:
            self.sleep_amount = max(0.001, self.sleep_amount * 0.95)
        elif total_data_points < 300:
            self.sleep_amount = min(0.05, self.sleep_amount * 1.0)
        time.sleep(self.sleep_amount)

# Custom client class for handling data stream


class MyClient(EasySeedLinkClient):
    def __init__(self, series, name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.series = series
        self.name = name
        self.stream = Stream()

    # Override method to handle incoming data
    def on_data(self, trace):
        self.stream += trace

        x_values_seconds = trace.times().tolist()
        start_time = trace.stats.starttime.timestamp * 1000
        x_values = [start_time + sec * 1000 for sec in x_values_seconds]
        y_values = trace.data.tolist()

        buffer.receive_data((x_values, y_values), self.name)


# Initialize data buffer for 3 clients
buffer = DataBuffer(3)

# Function to start a SeedLink client for a specific stream


def start_client(network, station, channel, series, name):
    client = MyClient(series, name, 'geofon.gfz-potsdam.de:18000')
    client.select_stream(network, station, channel)
    threading.Thread(target=client.run).start()
    return client


# List to store the clients
clients = []

# Loop through each client and start them
for i in range(3):
    client = start_client('MN', 'TRI', channels[i], series_list[i], name=i)
    clients.append(client)

# Main loop to add data to series continuously
while True:
    buffer.add_data_to_series()
    time.sleep(0.0045)
