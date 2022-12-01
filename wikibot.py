# wikibot.py

# Imports for pycord
import discord
from discord import option

# Imports for dotenv
import os
import dotenv

# Imports for data
from rswiki_wrapper import Latest, TimeSeries
import json
import pandas as pd
import matplotlib.pyplot as plt
import io

dotenv.load_dotenv()

debug_guild = os.getenv('DEBUG_GUILD')
bot = discord.Bot(debug_guilds=[debug_guild])
user_agent = os.getenv('USER_AGENT')


@bot.event
async def on_ready():
    await bot.sync_commands()
    print(f'We have logged in as {bot.user}')


@bot.slash_command(name='hello', description='Test Slash Commands and Say Hello')
async def hello(ctx):
    await ctx.respond("Hello!")


@bot.slash_command(description='Get latest real-time prices')
@option('ids',
        description='Specific IDs (separate with |) or blank for all',
        required=False,
        default='')
async def latest(ctx: discord.ApplicationContext,
                 ids: str):

    if len(ids) == 0:
        real_time = Latest(user_agent=user_agent)
    else:
        real_time = Latest(id=ids, user_agent=user_agent)

    await ctx.respond(json.dumps(real_time.content, indent=4))


@bot.slash_command(description='Generate historical pricing')
@option('id', description='Specific itemID', required=True)
@option('timestep', description='Step for time stamps (5m, 1hr, etc)', required=False, default='5m')
async def history(ctx: discord.ApplicationContext, id: str, timestep: str):

    timeseries = TimeSeries(id=id, timestep=timestep, user_agent=user_agent)

    # Format the data
    df = pd.DataFrame(timeseries.content)
    # Turn unix time into normal datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')

    # Initialize IO
    data_stream = io.BytesIO()

    # Do plotting
    plt.figure(figsize=(1, 1))
    trend = df.plot(x="timestamp", y=['avgHighPrice', 'avgLowPrice'])

    # Save content into the data stream
    plt.savefig(data_stream, format='png', bbox_inches="tight", dpi=80)
    plt.close()

    # Create file
    data_stream.seek(0)
    chart = discord.File(data_stream, filename="price_history.png")
    embed = discord.Embed()
    embed.set_image(url="attachment://price_history.png")

    await ctx.respond(file=chart, embed=embed)

bot.run(os.getenv('TOKEN'))
