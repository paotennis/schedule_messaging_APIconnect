from flask import Flask, request, abort
import os
import requests
import json
import re

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
import os

app = Flask(__name__)

#環境変数取得
YOUR_CHANNEL_ACCESS_TOKEN = os.environ["YOUR_CHANNEL_ACCESS_TOKEN"]
YOUR_CHANNEL_SECRET = os.environ["YOUR_CHANNEL_SECRET"]
TIME_TREE_ACCESS_TOKEN = os.environ["TIME_TREE_ACCESS_TOKEN"]

line_bot_api = LineBotApi(YOUR_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(YOUR_CHANNEL_SECRET)

timezone = 9

def convert_calendar(messages, calendar):
    start_date = messages[1]
    start_time = messages[2]
    end_date = messages[3]
    end_time = messages[4]
    plan_name = messages[5]

    start_year,start_month,start_day = start_date.split('/')
    start_hour,start_min = start_time.split(':')
    end_year,end_month,end_day = end_date.split('/')
    end_hour,end_min = end_time.split(':')

    timetree_dict = {
        "data": {
            "attributes": {
                "title": plan_name,
                "category": "schedule",
                "all_day": False,
                "start_at": start_year + "-" + start_month + "-" + start_day + "T" + start_hour + ":" + start_min + ":00.000Z",
                "end_at": end_year + "-" + end_month + "-" + end_day + "T" + end_hour + ":" + end_min + ":00.000Z"
            },
            "relationships": {
                "label": {
                    "data": {
                        "id": f"{calendar_id},1",
                        "type": "label"
                    }
                }
            }
        }
    }
    return timetree_dict

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
  messages = event.message.text.split()
  if "make" in messages[0]:
    if len(messages) != 6:
      reply = "Command: Not Found\nPlease input 'help'"
      line_bot_api.reply_message(event.reply_token,TextSendMessage(text = reply))
      return

    # header
    headers = {
    'Accept': 'application/vnd.timetree.v1+json',
    'Authorization': 'Bearer ' + TIME_TREE_ACCESS_TOKEN
    }

    URL = 'https://timetreeapis.com/calendars'
    
    #get json
    r = requests.get(URL, headers=headers)
    data = r.json()
    today = json.dumps(data, indent=4, ensure_ascii=False)
    
    #get calendar id
    p = r'"id": "(.*?)[,"]'
    r = re.findall(p, today)
    calendars=set(r)

    if len(messages[1].split('/')) != 3 or len(messages[2].split(':')) != 2 or len(messages[3].split('/')) != 3 or len(messages[4].split(':')) != 2:
      reply = "Command: Not Found\nPlease input 'help'"
      line_bot_api.reply_message(event.reply_token,TextSendMessage(text = reply))
      return
    
    make_message = convert_calendar(messages,calendars[0])

    json_data = json.dumps(make_message)
    response = requests.post("https://timetreeapis.com/calendars/" + calendars[0] + "/events",headers=headers, data=json_data)

    if response.status_code == 201:
        reply = "Success"
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text = reply))
        return
    else:
        reply = "Failed. Please retry."
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text = reply))
        return
    

  elif "see" in messages[0]:
    if len(messages) != 2:
      reply = "Command: Not Found\nPlease input 'help'"
      line_bot_api.reply_message(event.reply_token,TextSendMessage(text = reply))
      return
    
    try:
      daycount = int(messages[1])
    except ValueError:
      reply = "整数値で入力してください。"
      line_bot_api.reply_message(event.reply_token,TextSendMessage(text = reply))
      return
    
    if 0 < daycount < 7:
      # header
      headers = {
      'Accept': 'application/vnd.timetree.v1+json',
      'Authorization': 'Bearer ' + TIME_TREE_ACCESS_TOKEN
      }

      URL = 'https://timetreeapis.com/calendars'
      
      #get json
      r = requests.get(URL, headers=headers)
      data = r.json()
      today = json.dumps(data, indent=4, ensure_ascii=False)
      
      #get calendar id
      p = r'"id": "(.*?)[,"]'
      r = re.findall(p, today)
      calendars=set(r)
      
      messages = str(daycount) + "日後までのスケジュールです。\n"
      daycount += 1
        
      #get schedule
      for calendar in calendars:
        URL = 'https://timetreeapis.com/calendars/'+calendar+'/upcoming_events?timezone=Asia/Tokyo&days=' + str(daycount)
        r = requests.get(URL, headers=headers)
        data = r.json()
        for event in data['data']:
          start=event['attributes']['start_at']
          end=event['attributes']['end_at']
          
          # change format
          start_date,start_time = start.split("T")
          end_date,end_time = end.split("T")
          _,start_month,start_day = start_date.split("-")
          _,end_month,end_day = end_date.split("-")
          start_hour,start_min,_ = start_time.split(":")
          end_hour,end_min,_ = end_time.split(":")

          s_hour = int(start_hour) + timezone
          e_hour = int(end_hour) + timezone

          message = start_month + "/" + start_day + " "+ str(s_hour) + ":" + start_min + "～" + end_month + "/" + end_day + " "+ str(e_hour) + ":" + end_min + "\n" + event['attributes']['title'] + "\n"
          messages += message
      line_bot_api.push_message(USER_ID,TextSendMessage(text=message))
    else:
      reply = "Please input: 0 < daycount < 7"
      line_bot_api.reply_message(event.reply_token,TextSendMessage(text = reply))
      return

  elif "help" in messages[0]:
    reply = "makeコマンド:予定作成コマンド\n"+"Usage:\nmake\nYYYY/MM/DD hh:mm\nYYYY/MM/DD hh/mm\nname\n\n"
    reply = reply + "seeコマンド:予定閲覧コマンド\ndaycount(<7)日後までの予定を閲覧できます。\n"+"Usage:\nsee (daycount)"
    line_bot_api.reply_message(event.reply_token,TextSendMessage(text = reply))
    return

  else:
    reply = "Command: Not Found\nPlease input 'help'"
    line_bot_api.reply_message(event.reply_token,TextSendMessage(text = reply))
    return


if __name__ == "__main__":
#    app.run()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
