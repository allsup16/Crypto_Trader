from pathlib import Path
from datetime import time
import http.client
import json
import numpy as np
import uuid
import math

granularity_map = {
    "ONE_MINUTE": 60,
    "FIVE_MINUTE": 300,
    "FIFTEEN_MINUTE": 900,
    "ONE_HOUR": 3600,
    "SIX_HOUR": 21600,
    "ONE_DAY": 86400,
}


LOG_PATH = Path("log.json")
########### Interact with coinbase ##################### 
def MyAccountCurrencyOne(accounts,CurrencyOne):
    for x in accounts.accounts:
        if x.name == CurrencyOne:
            return x
    return 'Account not found'    
def MyValueCurrencyOne(client,accounts,CurrencyOne,ProductID):
    amount=0
    for x in accounts.accounts:
        if x.name == CurrencyOne:
            product = client.get_product(ProductID)
            amount=np.round(np.float64(product.price),decimals=0)*np.float64(x.available_balance['value'])
    return amount    
def MyValueCurrencyTwo(accounts,CurrencyTwo):
    amount=0
    for x in accounts.accounts:
        if x.name == CurrencyTwo:
            amount= np.float64(x.available_balance['value'])
    return amount    
def ValueProduct(client,ProductID):
    return np.float64(client.get_product(ProductID)['price'])
def OrderInfo(client,orderId):
    return client.get_order(orderId)
def BuyCurrencyOne(client, seed,ProductID): 
    print('Placing Buy Order...')
    try:
        order = client.market_order_buy(
            client_order_id=str(uuid.uuid4()), 
            product_id=ProductID, 
            quote_size=f"{seed:.8f}"  # buying $seed worth of BTC
        )
        print('Buy order placed:', order)
        return order
    except Exception as e:
        print("Buy failed:", e)
        return None
def SellCurrencyOneLimit(client,orderInfo,SeedSellThresh,PercentToSell):
    try: 
        clientId = str(uuid.uuid4())
        productId = orderInfo['order']['product_id']
        filledSize = float(orderInfo['order']['filled_size'])
        boughtPrice = float(orderInfo['order']['average_filled_price'])
        targetSalePrice = boughtPrice + boughtPrice * (SeedSellThresh / 100)
        filledSize = filledSize * (PercentToSell/100)
        limit_price = f"{targetSalePrice:.2f}"
        base_size = f"{filledSize:.8f}"
        order = client.limit_order_gtc_sell(
            client_order_id=clientId,
            product_id=productId,
            base_size=base_size,
            limit_price=limit_price,
            post_only=True)
        print("Sell Order: ",order)
        return order
    except Exception as e:
        print("Sell failed:", e)
        return None
def month_spread(client,Currency,granularity,days_back):
        seconds=granularity_map[granularity]#seconds in a day
        now = client.get_unix_time()
        end_ts = int(now["epoch_seconds"])
        start_ts = end_ts - (days_back * seconds)  # 30 days ago
        product = client.get_candles(Currency, start=start_ts, end=end_ts, granularity=granularity)
        high=0
        price=float(client.get_product(Currency)['price'])
        low = float('inf')
        for days in product['candles']:
            if float(days['low'])<low:
                low = float(days['low'])
            if float(days['high'])>high:
                high = float(days['high'])
        return price,low,high
######### Handles json files #####################
def scaling(accounts,instructions):
    value = MyValueCurrencyTwo(accounts,instructions['General_Instructions']['Currency_Two'])
    Dynamic_Scale=instructions['General_Instructions']['Scaling']
    fileLocation =  instructions['General_Instructions']['Json_File_Name']
    if value>Dynamic_Scale['Current_Base_Currency_Two'] and value<Dynamic_Scale['Cap_Amount']:
        scaleUp(instructions)
        instructions['General_Instructions']['Dynamic_Adjustment']['State']="Alt"
        WriteInstructions(fileLocation,instructions)

    elif value<Dynamic_Scale['Prev_Base_Currency_Two'] and Dynamic_Scale['Current_Base_Currency_Two']!=Dynamic_Scale['Min_Currency_Two']:
        scaleDown(instructions)
        instructions['General_Instructions']['Dynamic_Adjustment']['State']="Alt"
        WriteInstructions(fileLocation,instructions)

    return LoadInstructions(fileLocation)
def scaleUp(instructions):
    Dynamic_Scaling = instructions['General_Instructions']['Scaling']
    Plan = Dynamic_Scaling['Field_Groupings']
    
    
    if Dynamic_Scaling['Type'] == 'Stepping':
        for s in instructions['General_Instructions']['Field_Groupings'][Plan]:
            instructions['General_Instructions']['Dynamic_Adjustment']['States'][s]['Seed_Size'] += Dynamic_Scaling['Next_Seed_Size']
        
        Dynamic_Scaling['Prev_Base_Currency_Two']=Dynamic_Scaling['Current_Base_Currency_Two']
        Dynamic_Scaling['Prev_Seed_Size']=Dynamic_Scaling['Current_Seed_Size']
        Dynamic_Scaling['Current_Base_Currency_Two'] = Dynamic_Scaling['Next_Base_Currency_Two']
        Dynamic_Scaling['Current_Seed_Size'] = Dynamic_Scaling['Next_Seed_Size']
        Dynamic_Scaling['Next_Base_Currency_Two'] = Dynamic_Scaling['Next_Base_Currency_Two']+(Dynamic_Scaling['Next_Seed_Size']*Dynamic_Scaling['Scale_By'])
        Dynamic_Scaling['Next_Seed_Size'] = Dynamic_Scaling['Next_Seed_Size']+Dynamic_Scaling['Seed_Size_Change']



    if Dynamic_Scaling['Type'] == 'Linear':
        for s in instructions['General_Instructions']['Field_Groupings'][Plan]:
            instructions['General_Instructions']['Dynamic_Adjustment']['States'][s]['Seed_Size'] = Dynamic_Scaling['Next_Seed_Size']
        
        Dynamic_Scaling['Prev_Base_Currency_Two']=Dynamic_Scaling['Current_Base_Currency_Two']
        Dynamic_Scaling['Prev_Seed_Size']=Dynamic_Scaling['Current_Seed_Size']
        Dynamic_Scaling['Current_Base_Currency_Two'] = Dynamic_Scaling['Next_Base_Currency_Two']
        Dynamic_Scaling['Current_Seed_Size'] = Dynamic_Scaling['Next_Seed_Size']
        Dynamic_Scaling['Next_Base_Currency_Two'] = Dynamic_Scaling['Next_Base_Currency_Two']+Dynamic_Scaling['Scale_By']
        Dynamic_Scaling['Next_Seed_Size'] = Dynamic_Scaling['Next_Seed_Size']+Dynamic_Scaling['Seed_Size_Change']

def scaleDown(instructions):  
    Dynamic_Scaling = instructions['General_Instructions']['Scaling']
    Plan = Dynamic_Scaling['Field_Groupings']
    
    
    if Dynamic_Scaling['Type'] == 'Stepping':
        for s in instructions['General_Instructions']['Field_Groupings'][Plan]:
            instructions['General_Instructions']['Dynamic_Adjustment']['States'][s]['Seed_Size'] -= Dynamic_Scaling['Current_Seed_Size']
        Dynamic_Scaling['Next_Base_Currency_Two'] = Dynamic_Scaling['Current_Base_Currency_Two']
        Dynamic_Scaling['Next_Seed_Size'] = Dynamic_Scaling['Current_Seed_Size']
        Dynamic_Scaling['Current_Base_Currency_Two'] = Dynamic_Scaling['Prev_Base_Currency_Two']
        Dynamic_Scaling['Current_Seed_Size'] = Dynamic_Scaling['Prev_Seed_Size']
        Dynamic_Scaling['Prev_Seed_Size']=Dynamic_Scaling['Prev_Seed_Size']-Dynamic_Scaling['Seed_Size_Change']
        Dynamic_Scaling['Prev_Base_Currency_Two']=Dynamic_Scaling['Current_Base_Currency_Two']-(Dynamic_Scaling['Prev_Seed_Size']*Dynamic_Scaling['Scale_By'])
        if Dynamic_Scaling['Min_Seed_Size'] > Dynamic_Scaling['Prev_Seed_Size'] or  Dynamic_Scaling['Min_Currency_Two'] > Dynamic_Scaling['Prev_Base_Currency_Two']:
            Dynamic_Scaling['Prev_Seed_Size'] = Dynamic_Scaling['Min_Seed_Size']
            Dynamic_Scaling['Prev_Base_Currency_Two']= Dynamic_Scaling['Min_Currency_Two']
    
    
    if Dynamic_Scaling['Type'] == 'Linear':
        for s in instructions['General_Instructions']['Field_Groupings'][Plan]:
            instructions['General_Instructions']['Dynamic_Adjustment']['States'][s]['Seed_Size'] = Dynamic_Scaling['Prev_Seed_Size']
        Dynamic_Scaling['Next_Base_Currency_Two'] = Dynamic_Scaling['Current_Base_Currency_Two']
        Dynamic_Scaling['Next_Seed_Size'] = Dynamic_Scaling['Current_Seed_Size']
        Dynamic_Scaling['Current_Base_Currency_Two'] = Dynamic_Scaling['Prev_Base_Currency_Two']
        Dynamic_Scaling['Current_Seed_Size'] = Dynamic_Scaling['Prev_Seed_Size']
        Dynamic_Scaling['Prev_Seed_Size']=Dynamic_Scaling['Prev_Seed_Size']-Dynamic_Scaling['Seed_Size_Change']
        Dynamic_Scaling['Prev_Base_Currency_Two']=Dynamic_Scaling['Current_Base_Currency_Two']-Dynamic_Scaling['Scale_By']
        if Dynamic_Scaling['Min_Seed_Size'] > Dynamic_Scaling['Prev_Seed_Size'] or  Dynamic_Scaling['Min_Currency_Two'] > Dynamic_Scaling['Prev_Base_Currency_Two']:
            Dynamic_Scaling['Prev_Seed_Size'] = Dynamic_Scaling['Min_Seed_Size']
            Dynamic_Scaling['Prev_Base_Currency_Two']= Dynamic_Scaling['Min_Currency_Two']

def Dynamic_update(client,instructions):
    Currency=instructions['General_Instructions']['Product_ID']
    Granularity = instructions['General_Instructions']['Seed']['Granularity']
    DaysBack = instructions['General_Instructions']['Seed']['Days_Back']
    price,low,high=month_spread(client,Currency,Granularity,DaysBack)
    #Current State
    State = instructions['General_Instructions']['Dynamic_Adjustment']['State']
    instructions = Update(instructions,price,low,high,State)
    fileLocation =  instructions['General_Instructions']['Json_File_Name']
    WriteInstructions(fileLocation,instructions)
    return LoadInstructions(fileLocation)
def Update(general_instructions,price,low,high,State):
    #Modify State
    PercentLow = general_instructions['General_Instructions']['Dynamic_Adjustment']['Percent_Low']
    PercentHigh = general_instructions['General_Instructions']['Dynamic_Adjustment']['Percent_High']
    PercentMediumLow = general_instructions['General_Instructions']['Dynamic_Adjustment']['Percent_Medium_Low']
    PercentMediumHigh = general_instructions['General_Instructions']['Dynamic_Adjustment']['Percent_Medium_High']

    High_C = price+price*PercentHigh/100>high
    MHigh_C = price+price*PercentMediumHigh/100>high
    Low_C = low+low*PercentLow/100>price
    MLow_C = low+low*PercentMediumLow/100>price
    StateChange = "D"
    
    if  High_C: #(H:T) (MH:?) (ML:?) (L:?)
        StateChange = 'H'
    elif MHigh_C and not High_C: #(H:F) (MH:T) (ML:?) (L:?)
        StateChange = 'MH'
    elif Low_C and not MHigh_C and not High_C: #(H:F) (MH:F) (ML:?) (L:T)
        StateChange = 'L'
    elif MLow_C and not Low_C and not MHigh_C and not High_C: # (H:F) (MH:F) (ML:T) (L:F)
        StateChange = 'ML'

    if State != StateChange:
        general_instructions['General_Instructions']['Dynamic_Adjustment']['State'] = StateChange
        for field in general_instructions['General_Instructions']['Field_Groupings']['Dynamic_Adjustment']:
            general_instructions['General_Instructions']['Seed'][field] = general_instructions['General_Instructions']['Dynamic_Adjustment']['States'][StateChange][field]
    return general_instructions
def LoadInstructions(file_name):
    return json.loads(Path(f"{file_name}.json").read_text())
def WriteInstructions(file_name,altered):
    with open(Path(f"{file_name}.json"), 'w') as json_file:
        json.dump(altered, json_file, indent=4)
def load_log():
    if not LOG_PATH.exists():
        return []       
    text = LOG_PATH.read_text().strip()
    if not text:
        return []            
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        entries = []
        for line in text.splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries
def write_log_entry(entry: dict):
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(entry))
        f.write("\n")
######## Other ###################################
def Time_Conversion(hours):
    readable_times = [time(h).strftime("%#I:%M%p").lower() for h in hours]
    return readable_times