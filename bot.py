import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command, CommandObject
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from config import BOT_TOKEN
from utils import get_user, get_water_goal, get_calorie_goal, get_current_date, get_food_info

class Form(StatesGroup):
    name = State()
    weight = State()
    height = State()
    age = State()
    city = State()
    activity_level = State()
    calorie_goal = State()
    water_goal = State()
    cal_per_100 = State()

class Food(StatesGroup):
    food = State()
    cal_per_100 = State()
    food_grams = State()

# Создаем экземпляры бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Добро пожаловать! Я ваш бот.")

# Обработчик команды /help
@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer("Я могу ответить на команды /start, /help, /log_water, /log_food, /log_workout, /check_progress, /profile и /set_profile.")

@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    user = await get_user(message.from_user.id)

    await message.answer(
f"""Имя: {user['name']}
Вес: {user['weight']} кг.
Рост: {user['height']} см.
Возраст: {user['age']}
Уровень активности: {user['activity_level']} мин.
Цель по калориям: {user['calorie_goal']} ккал.
Цель по воде: {user['water_goal']} мл.
Город: {user['city']}
    """)

@dp.message(Command("log_water"))
async def cmd_log_water(message: Message, command: CommandObject):
    water_consumption = float(command.args)
    user = await get_user(message.from_user.id)
    city = user['city']
    cur_date = await get_current_date(city)
    daily_water_consumption = user.get(cur_date, {}).get('daily_water_consumption', 0)
    if user.get(cur_date, 0) == 0:
        user[cur_date] = {}
    user[cur_date]["daily_water_consumption"] = daily_water_consumption + water_consumption
    water_residual = (
        user['water_goal'] 
        - user[cur_date]['daily_water_consumption'] 
        + user[cur_date].get('additional_water_goal', 0)
    )
    await message.answer(
f"✅ Записано: {water_consumption:.1f} мл."
    )
    if water_residual > 0:
        await message.answer(
f"""До выполнения нормы сегодня осталось: {water_residual} мл.""")
    else:
        await message.answer(
"""Вы выполнили свою дневную норму!""")
        
@dp.message(Command("log_food"))
async def cmd_log_food(message: Message, state: FSMContext, command: CommandObject):
    food = command.args
    res = await get_food_info(food)
    name = res["name"]
    cal_per_100 = res["calories"]
    await state.update_data(
        food=food,
        cal_per_100=cal_per_100
    )
    await state.set_state(Food.food_grams)

    await message.answer(
        f"{name} — {cal_per_100} ккал на 100 г.\n"
        "Сколько грамм вы съели?"
    )

@dp.message(Food.food_grams)
async def process_grams(message: Message, state: FSMContext):
    grams = float(message.text.replace(",", "."))
    data = await state.get_data()
    food_consumption = data["cal_per_100"] * grams / 100

    user = await get_user(message.from_user.id)
    city = user['city']
    cur_date = await get_current_date(city)
    daily_calorie_consumption = user.get(cur_date, {}).get('daily_calorie_consumption', 0)
    if user.get(cur_date, 0) == 0:
        user[cur_date] = {}
    user[cur_date]["daily_calorie_consumption"] = daily_calorie_consumption + food_consumption
    food_residual = user['calorie_goal'] - user[cur_date]['daily_calorie_consumption']
    await message.answer(
f"✅ Записано: {food_consumption:.1f} ккал"
    )
    if food_residual > 0:
        await message.answer(
f"""До выполнения нормы сегодня осталось: {food_residual} ккал.""")
    else:
        await message.answer(
"""Вы выполнили свою дневную норму!""")

    await state.clear()

@dp.message(Command("log_workout"))
async def cmd_log_workout(message: Message, command: CommandObject):
    args = command.args.split()

    workout_type = args[0]
    mins = int(args[1])

    calories = mins * 10
    extra_water = 200 * mins / 30

    user = await get_user(message.from_user.id)
    city = user['city']
    cur_date = await get_current_date(city)

    user[cur_date]['additional_water_goal'] = user[cur_date].get('additional_water_goal', 0) + extra_water
    user[cur_date]['burned_calories'] = user[cur_date].get('burned_calories', 0) + calories

    text = (
        f"""{workout_type.capitalize()} {mins} минут — {calories} ккал.
💧 Дополнительно: выпейте {extra_water} мл воды."""
    )

    await message.answer(text)

@dp.message(Command("check_progress"))
async def cmd_check_progress(message: Message):
    user = await get_user(message.from_user.id)
    city = user['city']
    cur_date = await get_current_date(city)

    daily_water_consumption = user[cur_date].get('daily_water_consumption', 0)
    daily_calorie_consumption = user[cur_date].get('daily_calorie_consumption', 0)
    burned_calories = user[cur_date].get('burned_calories', 0)
    water_goal = user['water_goal'] + user[cur_date].get('additional_water_goal', 0)
    calorie_goal = user['calorie_goal']
    water_residual = water_goal - daily_water_consumption
    calorie_balance = daily_calorie_consumption - burned_calories
    await message.answer(
f"""📊 Прогресс:
Вода:
- Выпито: {daily_water_consumption} мл из {water_goal} мл.
- Осталось: {water_residual} мл.

Калории:
- Потреблено: {daily_calorie_consumption} ккал из {calorie_goal} ккал.
- Сожжено: {burned_calories} ккал.
- Баланс: {calorie_balance} ккал.
""")

@dp.message(Command("set_profile"))
async def cmd_set_profile(message: Message, state: FSMContext):
    await message.answer("Как вас зовут?")
    await state.set_state(Form.name)

@dp.message(Form.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer('Введите ваш рост (в см):')
    await state.set_state(Form.height)

@dp.message(Form.height)
async def process_height(message: Message, state: FSMContext):
    await state.update_data(height=message.text)
    await message.answer('Введите ваш вес:')
    await state.set_state(Form.weight)

@dp.message(Form.weight)
async def process_weight(message: Message, state: FSMContext):
    await state.update_data(weight=message.text)
    await message.answer('Введите ваш возраст:')
    await state.set_state(Form.age)

@dp.message(Form.age)
async def process_age(message: Message, state: FSMContext):
    await state.update_data(age=message.text)
    await message.answer('Сколько минут активности у вас в день?')
    await state.set_state(Form.activity_level)

@dp.message(Form.activity_level)
async def process_activity_level(message: Message, state: FSMContext):
    await state.update_data(activity_level=message.text)
    await message.answer('В каком городе вы находитесь?')
    await state.set_state(Form.city)

@dp.message(Form.city)
async def process_city(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    name = data.get("name")
    weight = int(data.get("weight"))
    height = int(data.get("height"))
    age = int(data.get("age"))
    activity_level = int(data.get("activity_level"))
    city = message.text

    user = await get_user(user_id)
    user['name'] = name
    user['height'] = height
    user['weight'] = weight
    user['age'] = age
    user['activity_level'] = activity_level
    user['city'] = city
    user['calorie_goal'] = await get_calorie_goal(user_id)
    user['water_goal'] = await get_water_goal(user_id)

    await state.clear()
    await message.answer("Профиль заполнен!")

# Основная функция запуска бота
async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())