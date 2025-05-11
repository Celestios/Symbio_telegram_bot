from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    TOKEN = os.getenv('TOKEN')
    database = './data/database.json'
    resources = './data/resources.json'
    ADMIN_ID = int(os.getenv('ADMIN_ID'))
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
    GROUP_ID = int(os.getenv('GROUP_ID'))
    G_ID_TA = os.getenv('G_TOPIC_ID_A')
    G_ID_TB = os.getenv('G_TOPIC_ID_B')
