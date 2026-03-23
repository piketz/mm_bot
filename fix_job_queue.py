with open('/home/ub/bot_uff_mm_prod/mm_bot.py', 'r') as f:
    content = f.read()

# Change ApplicationBuilder() to enable job queue
old = 'app = ApplicationBuilder().token(TOKEN).build()'
new = 'app = ApplicationBuilder().token(TOKEN).job_queue(job_queue).build()'

# We need to import job_queue first
old_import = 'from telegram.ext import ('
new_import = '''from telegram.ext import (
    ApplicationBuilder, JobQueue,'''

content = content.replace(old_import, new_import)

old_build = 'app = ApplicationBuilder().token(TOKEN).build()'
new_build = '''job_queue = JobQueue()
app = ApplicationBuilder().token(TOKEN).job_queue(job_queue).build()'''

content = content.replace(old_build, new_build)

with open('/home/ub/bot_uff_mm_prod/mm_bot.py', 'w') as f:
    f.write(content)

print("Job queue fix applied!")
