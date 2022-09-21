# trading-system

Trading simulator and client for automated trading.

## exchange-simulator

## Setup

If you haven't installed Python 3 yet, please download from [here](https://www.python.org/downloads/).

Create a virtual environment to install the Python dependencies

```sh
python3 -m venv automated-trading-venv
```

and activate it.

```sh
source ./automated-trading-venv/bin/activate
```

or if you are on Windows

```sh
automated-trading-venv\Scripts\activate.bat
```

Install the necessary dependencies

```sh
pip install -r requirements-dev.txt
```

### Run the server

and run the server from the root directory.

```sh
python -m simulator.main
```

All done, you can now connect to the server at `127.0.0.1:5000` and make requests.
You can also view the market at [127.0.0.1:5000/market](http://127.0.0.1:5000/market).
Enjoy!

### Run the client interactively

Make sure you are in the virtual environment and run an interactive Python shell.
Then import the module `import client`. This can be used to call the different
available functions.

Available functions:

* connect and disconnect: Connecting or disconnecting from the server
* status: Print status of current orders
* create: Create an order with these spces
* revise: Revise an existing order
* cancel: Cancel an existing order

You can run `help(<function>)` to check the signature.

Example:

```py
>>> import client
>>> client.create_iceberg(side=client.Side.Buy, quantity=100, limit_price=10, slice_size=10)
>>> client.status()
Completed orders:
[]
Pending orders:
[{'filled_quantity': 0,
  'iceberg_order': {'state': <State.Sent: 'Sent'>, 'message_id': '97d5b4d236004b21a8b7b4430ddf1428', 'order_id': '880ee4f16766410498390c1ca89a78e0', 'side': <Side.Buy: 'buy'>, 'limit_price': 10, 'slice_size': 10, 'slice_filled_quantity': 0},
  'limit_price': 10,
  'parent_id': '229d70abd2be4386b15d93d84dac411b',
  'quantity': 100,
  'side': <Side.Buy: 'buy'>,
  'state': <State.Sent: 'Sent'>,
  'updated_at': datetime.datetime(2022, 9, 15, 19, 12, 59, 65460)}]
>>> client.disconnect()
>>> exit()
```

Tail the client logs through `tail -f  trading_app.log` and the simulator logs
through `tail -f exch_simulator.log`.
