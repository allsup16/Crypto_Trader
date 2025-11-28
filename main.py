from coinbase.rest import RESTClient
from dotenv import load_dotenv
from datetime import datetime,timezone
import traceback
import os
import helper
import time

load_dotenv()

api_key = os.getenv('Coinbase_API_Key_Name')
api_secret = os.getenv('Coinbase_Private_Key')
#with open("/root/auto_staker/logs/cron.log", "a") as log:                                                                   
#    log.write(f"\n[{datetime.now(timezone.utc)}] main.py started\n")

Files=["Coinbase_Long_BTC_Instructions"]#"Coinbase_Short_BTC_Instructions"]

def main(file):
    try:
        client = RESTClient(api_key=api_key,api_secret=api_secret)
        accounts = client.get_accounts()
        instructions=helper.LoadInstructions(file)
        ProductId=instructions['General_Instructions']['Product_ID']
        CurrencyOne=instructions['General_Instructions']['Currency_One']
        CurrencyTwo=instructions['General_Instructions']['Currency_Two']

        if instructions['General_Instructions']['Scaling']['Active']:
            helper.scaling(accounts,instructions)
        
        if instructions['General_Instructions']['Dynamic_Adjustment']['Active']:
            instructions=helper.Dynamic_update(client,instructions)

        
        Active = instructions['General_Instructions']['Manual_Stop']       
        Timer = instructions['General_Instructions']['Timer']
        Count = instructions['General_Instructions']['Counter']
        CounterMax = instructions['General_Instructions']['Counter_Max']

        ActiveBuy = instructions['General_Instructions']['Seed']['Active_Buy']
        Counter = instructions['General_Instructions']['Seed']['Trigger']
        SeedSize = instructions['General_Instructions']['Seed']['Seed_Size']
        ActiveSell = instructions['General_Instructions']['Seed']['Active_Sell']
        
        SeedSellThresh = instructions['General_Instructions']['Seed']['Sell_Threshold_Percentage']
        PecentToBeSold = instructions['General_Instructions']['Seed']['Percent_To_Be_Sold']
        Min=instructions['General_Instructions']['Seed']['Minimum_Currency_Two']
        
        value =helper.MyValueCurrencyTwo(accounts,CurrencyTwo)
        if Active:
            print(value >= Min)
            if value >= Min:
                if Count%Counter==0:
                    if ActiveBuy:
                        buyReply = helper.BuyCurrencyOne(client,SeedSize,ProductId)
                        print(buyReply)
                        time.sleep(Timer)
                        orderId = buyReply['success_response']['order_id']
                        orderInfo = helper.OrderInfo(client,orderId)
                        if ActiveSell:
                            sellReply=helper.SellCurrencyOneLimit(client,orderInfo,SeedSellThresh,PecentToBeSold)
                            print(sellReply)

            if  instructions['General_Instructions']['Counter']+1<=CounterMax:
                instructions['General_Instructions']['Counter']+=1
                print('reaches')
            else:
                instructions['General_Instructions']['Counter']=1
            print(instructions)
            helper.WriteInstructions(file,instructions)
        time.sleep(instructions['General_Instructions']['Timer'])
    except Exception as e:
            print("".join(traceback.format_exception(type(e), e, e.__traceback__)))

if __name__ == "__main__":
    for f in Files:
        main(f)