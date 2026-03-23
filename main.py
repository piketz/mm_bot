import json
import os
import re
import time
from datetime import datetime, timedelta

import pandas as pd
from telegram import ReactionTypeEmoji, Update
from telegram.ext import (ApplicationBuilder, CommandHandler, ContextTypes,
                          MessageHandler, filters)

# -------------------------------------------------
