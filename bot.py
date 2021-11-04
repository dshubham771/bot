import sys
sys.path.append("/usr/local/lib/python3.9/site-packages")
from xlwt import Workbook
wb = Workbook()
sheet = wb.add_sheet('Order Book', cell_overwrite_ok=True)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
s = Service(ChromeDriverManager().install())
from bs4 import BeautifulSoup
import secrets
import json
from websocket import create_connection
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException
import math
import time

blacklist = ["REEFBTC", "CELRBTC", "VIBBTC", "ETCBTC", "COSBTC", "PHBBTC", "DGBBTC", "ADABTC", "ETHBTC", "SOLBTC", "MATICBTC"]

sheet.write(0, 0, "Coin")
sheet.write(0, 1, "Qty")
sheet.write(0, 3, "Buy Price")
sheet.write(0, 4, "Sell Price")
sheet.write(0, 6, "Pnl amount")
sheet.write(0, 7, "Pnl %")
sheet.write(0, 9, "Capital Used")

sheet.write(0, 11, "Recent Vol %")
sheet.write(0, 12, "Pings")
sheet.write(0, 13, "Net Vol %")

sheet.write(0, 15, "Buy time")
sheet.write(0, 16, "Sell time")

client = Client("QoukvJkask8R91Ql1A122wtuW1IykLIDcmBYFdav1ftrqEyPY5XkrtAOTqkZDP3l",
                "EC1kzfy9K8R5hqyJHYEEPdfvrRNHLYa1oqDhi17svEXutjWy4HCYRVQndHlVWYfr")

profit_percentage = 1
stoploss_percentage = 1.5
trail_stoploss_percentage = 0.2

coin_recent_vol_percentage = 0
coin_pings = 0
coin_net_vol_percentage = 0

op = webdriver.ChromeOptions()
op.add_argument('--headless')

driver = webdriver.Chrome(options=op, service=s)

profit = 0
file_log = open("guru.txt", "w+")
prcount = 0
lscouunt = 0

SIDE_BUY = 'BUY'
SIDE_SELL = 'SELL'

ORDER_TYPE_LIMIT = 'LIMIT'
ORDER_TYPE_MARKET = 'MARKET'
ORDER_TYPE_STOP_LOSS = 'STOP_LOSS'
ORDER_TYPE_STOP_LOSS_LIMIT = 'STOP_LOSS_LIMIT'
ORDER_TYPE_TAKE_PROFIT = 'TAKE_PROFIT'
ORDER_TYPE_TAKE_PROFIT_LIMIT = 'TAKE_PROFIT_LIMIT'
ORDER_TYPE_LIMIT_MAKER = 'LIMIT_MAKER'

TIME_IN_FORCE_GTC = 'GTC'  # Good till cancelled
TIME_IN_FORCE_IOC = 'IOC'  # Immediate or cancel
TIME_IN_FORCE_FOK = 'FOK'  # Fill or kill
TIME_IN_FORCE_GTX = 'GTX'  # Post only order

res = client.get_exchange_info()


def check_availability(order_coin_name):
    for item in res['symbols']:
        if item['symbol'] == order_coin_name.upper():
            return True
    return False


def truncate(f, n):
    return math.floor(f * 10 ** n) / 10 ** n


def get_percent(order_coin_name):
    tickers = client.get_ticker(symbol=order_coin_name)
    latest_percnt_change = float(tickers['priceChangePercent'])
    return latest_percnt_change


def get_quantity_in_precison(order_coin_name, qty):
    # print(client.get_account_snapshot())
    # print(" here ",client.get_symbol_info(order_coin_name),order_coin_name)
    dc = client.get_symbol_info(order_coin_name)
    n = int(dc['baseAssetPrecision'])
    # qty ="{:f}".format(truncate(qty,n))
    # print(qty,type(qty))
    step_size = 0
    filters = dc['filters']
    for f in filters:
        # print("filter~~~~~~~~~~~~ " + str(f))
        if f['filterType'] == 'LOT_SIZE':
            step_size = float(f['stepSize'])

    # bal = self._client.get_asset_balance(asset='BNB')
    # quantity = (float(bal['free']))/self._price*0.9995

    min_qty = client.get_symbol_info(order_coin_name)['filters'][5]['minQty']  # to get min qty of coin
    min_qty = float(min_qty)
    max_qty = client.get_symbol_info(order_coin_name)['filters'][5]['maxQty']  # max
    max_qty = float(max_qty)

    qty2 = float(qty)
    # print(min_qty,max_qty,qty)
    precise = len(str(min_qty).split('.')[1])
    qty2 = truncate(qty, precise)
    if step_size:
        precision = int(round(-math.log(step_size, 10), 0))
        quantity = float(truncate(qty, precision))
        return "{:f}".format(min(qty2, truncate(quantity, step_size)))
    return "{:f}".format(min(truncate(qty, 8), qty2))


def round_down(coin, number):
    number = float(number)
    info = client.get_symbol_info(coin)
    step_size = [float(_['stepSize']) for _ in info['filters'] if _['filterType'] == 'LOT_SIZE'][0]
    step_size = '%.8f' % step_size
    step_size = step_size.rstrip('0')
    decimals = len(step_size.split('.')[1])
    return math.floor(number * 10 ** decimals) / 10 ** decimals


def cancel_order(order_coin_name, oid):
    return client.cancel_order(symbol=order_coin_name, orderId=oid)


def get_filtered_price(order_coin_name, price):
    mp = client.get_symbol_info(order_coin_name)['filters'][0]['minPrice']
    decimalPts = len(mp.rstrip('0').split('.')[1])
    price = "{:f}".format(truncate(price, decimalPts))
    print("new limit price set ", price)
    return price


# def get_price(coin):
#      return float(client.get_ticker(symbol=coin)['lastPrice'])

def get_price(order_coin_name):
    # print("Check one")
    ws = create_connection("wss://stream.binance.com:9443/ws/" + order_coin_name.lower() + "@trade")
    result = ws.recv()
    result = json.loads(result)
    ws.close()
    # print("check two")
    return float(result['p'])


def get_free_asset(coin):
    balance = float(client.get_asset_balance(asset=coin)['free'])

    # balance ="{:f}".format(balance)
    return balance


def check_valid_qty(order_coin_name, qty):
    min_qty = client.get_symbol_info(order_coin_name)['filters'][5]['minQty']  # to get min qty of coin
    min_qty = float(min_qty)
    max_qty = client.get_symbol_info(order_coin_name)['filters'][5]['maxQty']  # max
    max_qty = float(max_qty)

    qty = float(qty)
    # print(min_qty,max_qty,qty)
    precise = len(str(min_qty).split('.')[1])
    qty = truncate(qty, precise)
    if min_qty >= qty:
        return False
    if max_qty < qty:
        return False

    return True


def average_of_market_order(fills):
    qty = 0
    tcost = 0
    for trade in fills:
        qty += float(trade['qty'])
        tcost += float(trade['qty']) * float(trade['price'])

    return tcost / qty


def convert_volume(coin, quantity, last_price):
    """Converts the volume given in QUANTITY from BTC to the each coin's volume"""

    quantity = float(quantity)
    last_price = float(last_price)
    try:
        info = client.get_symbol_info(coin)
        step_size = info['filters'][2]['stepSize']
        lot_size = {coin: step_size.index('1') - 1}

        if lot_size[coin] < 0:
            lot_size[coin] = 0

    except:
        print("Ran except block for lot size")
        lot_size = {coin: 0}
        pass

    # print(lot_size[coin])
    # calculate the volume in coin from QUANTITY in USDT (default)
    volume = float(quantity / float(last_price))

    # define the volume with the correct step size
    if coin not in lot_size:
        volume = float('{:.1f}'.format(volume))

    else:
        # if lot size has 0 decimal points, make the volume an integer
        if lot_size[coin] == 0:
            volume = int(volume)
        else:
            volume = float('{:.{}f}'.format(volume, lot_size[coin]))
    #  print(volume,float(info['filters'][2]['minQty'])," inside convert")
    #  volume=max(volume,float(info['filters'][2]['minQty']))
    return volume


def create_buy_order(coin, qty):
    """
    Creates simple buy order and returns the order
    """
    return client.create_order(
        symbol=coin,
        side=SIDE_BUY,
        type='MARKET',
        quantity=qty
    )


def create_sell_order(coin, qty):
    """
    Creates simple buy order and returns the order
    """
    return client.create_order(
        symbol=coin,
        side=SIDE_SELL,
        type='MARKET',
        quantity=qty
    )


def create_limit_sell_order(coin, qty, pr):
    """
    Creates simple buy order and returns the order
    """
    # print(qty,type(qty))
    return client.create_order(
        symbol=coin,
        side=SIDE_SELL,
        type=ORDER_TYPE_LIMIT,
        quantity=qty,
        timeInForce=TIME_IN_FORCE_GTC,
        price=pr
    )


def create_limit_buy_order(coin, qty, pr):
    """
    Creates simple buy order and returns the order
    """
    # print(qty,type(qty))
    return client.create_order(
        symbol=coin,
        side=SIDE_BUY,
        type=ORDER_TYPE_LIMIT,
        quantity=qty,
        timeInForce=TIME_IN_FORCE_GTC,
        price=pr
    )


def get_order_status(order_coin_name, target_order_id):
    return client.get_order(symbol=order_coin_name, orderId=target_order_id)["status"]


def run_starter():
    global client

    client = Client("QoukvJkask8R91Ql1A122wtuW1IykLIDcmBYFdav1ftrqEyPY5XkrtAOTqkZDP3l",
                    "EC1kzfy9K8R5hqyJHYEEPdfvrRNHLYa1oqDhi17svEXutjWy4HCYRVQndHlVWYfr")

    op = webdriver.ChromeOptions()
    op.add_argument('--headless')
    global driver

    driver = webdriver.Chrome(options=op, service=s)
    global SIDE_BUY
    SIDE_BUY = 'BUY'

    global SIDE_SELL
    SIDE_SELL = 'SELL'

    global ORDER_TYPE_LIMIT
    ORDER_TYPE_LIMIT = 'LIMIT'
    global ORDER_TYPE_MARKET
    ORDER_TYPE_MARKET = 'MARKET'
    global ORDER_TYPE_STOP_LOSS
    ORDER_TYPE_STOP_LOSS = 'STOP_LOSS'

    global TIME_IN_FORCE_GTC
    TIME_IN_FORCE_GTC = 'GTC'  # Good till cancelled

    global TIME_IN_FORCE_IOC
    TIME_IN_FORCE_IOC = 'IOC'  # Immediate or cancel

    global TIME_IN_FORCE_FOK
    TIME_IN_FORCE_FOK = 'FOK'  # Fill or kill

    global TIME_IN_FORCE_GTX
    TIME_IN_FORCE_GTX = 'GTX'  # Post only order

    global profit

    profit = 0
    global prcount
    prcount = 0
    global btc_price
    btc_price = get_price("BTCUSDT")
    global lscouunt
    lscouunt = 0
    global file_log
    file_log = open("guru.txt", "w+")


def get_token_to_be_baught():
    print("finding tokens")

    driver.get("http://agile-cliffs-23967.herokuapp.com/binance")

    content = driver.page_source
    try:
        soup = BeautifulSoup(content, "html5lib")
    except Exception as e:
        print(str(e))

    ls = []
    #     print("here")
    for a in soup.findAll('tr', attrs={'class': 'coin'}):
        # print(a)
        ln = a.find('a')
        link = ln.get("href")
        pair = link.split("/")[-1]
        newlink = link[:-3] + "USDT"
        print(pair, newlink)
        count = 0
        pings = 0
        net_vol_percentage = 0
        recent_vol_percentage = 0
        recent_net_volume = 0

        coin_symbol, base_coin = pair.split("_")
        base_coin = "USDT"
        coin_name = coin_symbol + base_coin

        if not check_availability(coin_name):
            continue

        tickers = client.get_ticker(symbol=coin_name)
        percent_change_price = tickers['priceChangePercent']
        percent_change_price = float(percent_change_price)

        for dt in a.find_all("th"):
            #
            new_data = dt.text.replace('\n', ' ').strip()
            # print(new_data)
            if count == 1:
                pings = int(new_data)
            elif count == 2:
                net_vol_btc = float(new_data)
            elif count == 3:
                net_vol_percentage = float(new_data[:-1])
            elif count == 5:
                recent_vol_percentage = float(new_data[:-1])
            elif count == 6:
                recent_net_volume = float(new_data)
                # print(recent_net_volume)

            count += 1

        print(coin_name)
        if (recent_vol_percentage > 0.7 and pings > 3 and pings < 10 and net_vol_percentage > 0.8):
            print("chosen ", pair)
            ls.append([coin_name, percent_change_price, coin_symbol, base_coin, recent_vol_percentage, pings,
                       net_vol_percentage])

    # ls.sort(key=lambda x:-x[1])

    # print("returning list: ", ls)
    return ls


btc_price = 60000  # get_price("BTCUSDT")

# run_starter()
row = 1
pnl = 0
total_pnl_amount = 0


def placeBuyOrderExcel(coin, qty, price):
    global pnl
    pnl = qty * price
    sheet.write(row, 0, coin)
    sheet.write(row, 1, qty)
    sheet.write(row, 3, price)
    sheet.write(row, 9, price * qty)  # capital used

    sheet.write(row, 11, coin_recent_vol_percentage)
    sheet.write(row, 12, coin_pings)
    sheet.write(row, 13, coin_net_vol_percentage)

    t = time.localtime()
    sheet.write(row, 15, time.strftime("%H:%M:%S", t))
    wb.save('orderBookExcel.xls')


def placeSellOrderExcel(coin, qty, price):
    global row
    global pnl
    global total_pnl_amount
    pnlAmount = qty * price - pnl
    pnlPercentage = pnlAmount / pnl * 100

    sheet.write(row, 4, price)
    sheet.write(row, 6, pnlAmount)
    sheet.write(row, 7, pnlPercentage)

    t = time.localtime()
    sheet.write(row, 16, time.strftime("%H:%M:%S", t))

    total_pnl_amount += pnlAmount
    sheet.write(row + 1, 6, total_pnl_amount)  # total of pnl in last row
    row += 1
    wb.save('orderBookExcel.xls')


#############################################################################################################################################################
########################################################################   BOT FUNCTION   ###################################################################
#############################################################################################################################################################
def bot():
    global prcount
    prcount = 0

    global limit_order_count
    limit_order_count = 0
    order_number = 1

    wait_for_long = 0
    print("\n=========================  BOT Started  =========================\n")
    global coin_recent_vol_percentage
    global coin_pings
    global coin_net_vol_percentage

    while True:

        ls = get_token_to_be_baught()
        if not ls:
            print("Wait 5 sec")
            time.sleep(5)
            continue
        else:
            print("received list: ", ls)
            taken_secret = secrets.choice(ls)
            order_coin_name = taken_secret[0]
            base_coin = taken_secret[3]
            coin_recent_vol_percentage = taken_secret[4]
            coin_pings = taken_secret[5]
            coin_net_vol_percentage = taken_secret[6]

        available_USDT = 25  # get_free_asset("USDT")
        print(available_USDT)
        usage_for_first_trade = 1
        if base_coin == "BTC":
            amount_allotted = float(get_free_asset("BTC")) * usage_for_first_trade
        else:
            amount_allotted = available_USDT * usage_for_first_trade

        quote_length = 3
        if order_coin_name[-4:] == "USDT":
            quote_length = 4

        quantity = 0

        float_coin_price = get_price(order_coin_name)
        quantity = convert_volume(order_coin_name, amount_allotted, float_coin_price)
        base_quantity = quantity

        if not check_valid_qty(order_coin_name, base_quantity):
            print("Re enter Qty not following min max")
            # file_log.write("\n "+str(e))
            continue

        try:
            global original_limit
            placeBuyOrderExcel(order_coin_name, base_quantity, float_coin_price)
            print("bought " + order_coin_name + " avg buy price " + str(float_coin_price))
            startTime = time.time()

            original_limit = float_coin_price * (1 + profit_percentage / 100)

            file_log.write(
                "\n \nOrder " + str(order_number) + " placed :" + order_coin_name + " average buy price " + str(
                    float_coin_price) + " Limit sell at " + str(float_coin_price * (1 + profit_percentage / 100)))
            file_log.write(
                "\nCoin parameters: Recent Volume % = " + str(coin_recent_vol_percentage) + " Pings = " + str(
                    coin_pings) + " Net Volume % = " + str(coin_net_vol_percentage))
            file_log.flush()
            order_number += 1

        except Exception as e:
            print(e)
            file_log.write("\n " + str(e))
            run_starter()
            continue

        limit_price = float_coin_price * (1 + profit_percentage / 100)

        sold = 0
        limit_order_count = 0
        time_start = time.time()
        net_quantity = base_quantity
        while not sold:
            # print("INSIDE TRADE")
            time.sleep(1)
            lastPrice = get_price(order_coin_name)

            print("Avg buy ", float_coin_price, " Current price ", lastPrice, " Limit sell at ", limit_price,
                  "Stoploss at ", (1 - stoploss_percentage / 100) * float_coin_price)

            if lastPrice >= limit_price:

                print("inside profit cell ")
                file_log.write("\n *** Inside profit cell  ***")
                file_log.flush()
                prev_last_price = limit_price

                # lastPrice=get_price(order_coin_name)
                # print(limit_price,lastPrice)
                flag = 0
                maxPrice = lastPrice
                try:
                    while True:
                        time.sleep(1)
                        lastPrice = get_price(order_coin_name)
                        print("\nInside profit : Avg buy ", float_coin_price, " Current price ", lastPrice,
                              " Limit sell at ", maxPrice)
                        if lastPrice > limit_price:
                            limit_price = lastPrice
                            maxPrice = max(lastPrice, maxPrice)
                            file_log.write("\nLimit trailed to :" + str(limit_price))
                            file_log.flush()

                        elif lastPrice < original_limit * 0.98 or lastPrice < (maxPrice-original_limit) * 0.85:
                            file_log.write("max price = "+str(maxPrice)+"\nTrail stoploss hit ✅, Placing sell order now!" + str(limit_price))
                            file_log.flush()
                            break
                        elif time.time() - startTime > 60*60*2:
                            file_log.write("max price = "+str(maxPrice)+"\nTime limit exceeded while trailing, Placing sell order now!" + str(limit_price))
                            file_log.flush()
                            break

                    placeSellOrderExcel(order_coin_name, net_quantity, lastPrice)
                    # print("executed")
                    selling_price = maxPrice

                    file_log.write("\n*** ❤️profit❤️  ***  bought at " + str(float_coin_price) + " sold at " + str(
                        lastPrice) + " **** \n")
                    file_log.write("\n\nTotal pnl till now is : ====>> " + str(total_pnl_amount) + " $\n")
                    file_log.flush()
                    print("\n* profit bought at " + str(float_coin_price) + " sold at " + str(lastPrice) + " *")
                    sold = 1

                    time.sleep(2)
                    continue

                except Exception as e:
                    print(e)
                file_log.flush()
                prcount += 1

            elif limit_order_count == 0 and float(lastPrice) < float_coin_price - (float_coin_price * 1 / 100):
                limit_order_count += 1
                try:
                    file_log.write("\n updating limit sell order" + str(limit_order_count))
                    file_log.flush()
                except Exception as e:
                    # run_starter()
                    file_log.write("\n " + str(e))
                    print(e)

                quantity_so_far = quantity
                quantity = base_quantity * 2
                net_quantity = quantity_so_far + quantity
                float_coin_price = (lastPrice * quantity + float_coin_price * quantity_so_far) / (net_quantity)
                placeBuyOrderExcel(order_coin_name, net_quantity, float_coin_price)
                limit_price = 1.01 * float_coin_price
                print("\nLimit 1  avg buy ", float_coin_price, " current price ", lastPrice, " limit sell at ",
                      limit_price)
                file_log.write(
                    "\n Limit 1  avg buy price " + str(float_coin_price) + " current price " + str(lastPrice))
                file_log.flush()


            elif limit_order_count == 1 and float(lastPrice) < float_coin_price - (float_coin_price * 2 / 100):
                limit_order_count += 1
                try:
                    file_log.write("\n updating limit sell order" + str(limit_order_count))
                    file_log.flush()
                except Exception as e:
                    # run_starter()
                    file_log.write("\n " + str(e))
                    print(e)

                quantity_so_far = quantity
                quantity = base_quantity * 4
                net_quantity = quantity_so_far + quantity
                float_coin_price = (lastPrice * quantity + float_coin_price * quantity_so_far) / (net_quantity)
                limit_price = 1.01 * float_coin_price
                placeBuyOrderExcel(order_coin_name, net_quantity, float_coin_price)
                print("Limit 2  avg buy ", float_coin_price, " current price ", lastPrice, " limit sell at ",
                      limit_price)
                file_log.write(
                    "\n Limit 2  avg buy price " + str(float_coin_price) + " current price " + str(lastPrice))
                file_log.flush()

            elif limit_order_count == 2 and float(lastPrice) < float_coin_price - (float_coin_price * 4 / 100):
                limit_order_count += 1
                try:
                    file_log.write("\n updating limit sell order" + str(limit_order_count))
                    file_log.flush()
                except Exception as e:
                    # run_starter()
                    file_log.write("\n " + str(e))
                    print(e)

                quantity_so_far = quantity
                quantity = base_quantity * 8
                net_quantity = quantity_so_far + quantity
                float_coin_price = (lastPrice * quantity + float_coin_price * quantity_so_far) / (net_quantity)
                limit_price = 1.01 * float_coin_price
                placeBuyOrderExcel(order_coin_name, net_quantity, float_coin_price)
                print("\nLimit 3  avg buy ", float_coin_price, " current price ", lastPrice, " limit sell at ",
                      limit_price)
                file_log.write(
                    "\n Limit 3  avg buy price " + str(float_coin_price) + " current price " + str(lastPrice))
                file_log.flush()


            if time.time() - startTime > 60*60*2:
                balance = get_free_asset(order_coin_name[:-quote_length])
                # balance=get_quantity_in_precison(order_coin_name,balance)
                # lastPrice=average_of_market_order(placed_order['fills'])
                print("\n--->Time limit exceeded  --> loss")
                placeSellOrderExcel(order_coin_name, net_quantity, lastPrice)
                file_log.write("\n--->Time limit exceeded --> loss ☹️ ==> buy price " + str(
                    float_coin_price) + " sell price " + str(lastPrice))
                file_log.flush()
                sold = 1


run_starter()
try:

    bot()
except Exception as e:
    file_log.write(str(e))
