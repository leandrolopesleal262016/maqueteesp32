from machine import Pin, PWM, Timer, freq
import json
import time
import os
import gc
import _thread

freq(240000000)  # Aumenta a frequência da CPU

CONFIG_FILE = 'motor_config.json'

def log_message(message):
    print(f"[{time.time()}] {message}")

class ServoMotor:
    def _init_(self, pin):
        self.pwm = PWM(Pin(pin), freq=50)
        self.inverted = (pin == 32)
        self.set_angle(0)
        
    def set_angle(self, angle):
        if self.inverted:
            angle = 180 - angle
        duty = int(((angle / 180) * 110 + 20))
        log_message(f"Ajustando ServoMotor para ângulo {angle}° (duty: {duty})")
        self.pwm.duty(duty)

class StepperMotor:
    def _init_(self, pin1, pin2, pin3, pin4, name, timer_id):
        self.pins = [Pin(pin1, Pin.OUT), Pin(pin2, Pin.OUT), 
                     Pin(pin3, Pin.OUT), Pin(pin4, Pin.OUT)]
        self.step_sequence = [
            [1, 1, 0, 0],
            [0, 1, 1, 0],
            [0, 0, 1, 1],
            [1, 0, 0, 1]
        ]
        self.step_count = 0
        self.name = name
        self.is_running = False
        self.direction = 1
        self.timer = Timer(timer_id)
        self.speed = 2
        self.rotation_time = 5
        self.steps_per_revolution = 2048
        self.stop()
        log_message(f"Motor {self.name} configurado - Pinos: {pin1}, {pin2}, {pin3}, {pin4}")

    def step(self, t=None):
        if self.is_running:
            for i in range(4):
                self.pins[i].value(self.step_sequence[self.step_count][i])
            self.step_count = (self.step_count + self.direction) % 4

    def start_rotation(self, direction, duration):
        log_message(f'Motor {self.name} - Iniciando rotação, direção: {direction}, duração: {duration}s')
        if not self.is_running:
            self.direction = direction
            self.is_running = True
            self.timer.init(period=self.speed, mode=Timer.PERIODIC, callback=self.step)
            time.sleep(duration)
            self.stop()

    def stop(self):
        if hasattr(self, 'timer'):
            self.timer.deinit()
        self.is_running = False
        for pin in self.pins:
            pin.value(0)
        time.sleep_ms(20)
        log_message(f'Motor {self.name} - Parado')

def check_buttons():
    button1 = Pin(25, Pin.IN, Pin.PULL_UP)
    button2 = Pin(26, Pin.IN, Pin.PULL_UP)
    button3 = Pin(4, Pin.IN, Pin.PULL_UP)
    button4 = Pin(5, Pin.IN, Pin.PULL_UP)
    
    last_press = {'output1': 0, 'output2': 0, 'output3': 0, 'output4': 0}
    debounce_time = 200  # ms
    
    log_message("Sistema de botões iniciado")
    
    while True:
        current_time = time.ticks_ms()
        
        if not button1.value() and time.ticks_diff(current_time, last_press['output1']) > debounce_time:
            log_message("Botão 1 pressionado")
            operate_gate('output1')
            last_press['output1'] = current_time
        
        if not button2.value() and time.ticks_diff(current_time, last_press['output2']) > debounce_time:
            log_message("Botão 2 pressionado")
            operate_gate('output2')
            last_press['output2'] = current_time
                
        if not button3.value() and time.ticks_diff(current_time, last_press['output3']) > debounce_time:
            log_message("Botão 3 pressionado")
            operate_gate('output3')
            last_press['output3'] = current_time
                
        if not button4.value() and time.ticks_diff(current_time, last_press['output4']) > debounce_time:
            log_message("Botão 4 pressionado")
            operate_gate('output4')
            last_press['output4'] = current_time
                
        time.sleep_ms(50)

def operate_gate(output_id):
    log_message(f"Operando portão: {output_id}")
    try:
        if output_id in ['output1', 'output2', 'output3']:
            motor_control = motors[output_id]
            if not motor_control['motor'].is_running:
                motor_control['state'] = True
                motor = motor_control['motor']
                
                # Inverte a rotação apenas para o portão 1
                if output_id == 'output1':
                    motor.start_rotation(-1, motor.rotation_time)
                    time.sleep(2)
                    motor.start_rotation(1, motor.rotation_time)
                else:
                    motor.start_rotation(1, motor.rotation_time)
                    time.sleep(2)
                    motor.start_rotation(-1, motor.rotation_time)

                motor_control['state'] = False

        elif output_id == 'output4':
            motors[output_id]['state'] = True
            servos = motors[output_id]['servos']
            for angle in range(0, 76, 2):
                for servo in servos:
                    servo.set_angle(angle)
                time.sleep(0.04)
            time.sleep(3)
            for angle in range(76, -1, -2):
                for servo in servos:
                    servo.set_angle(angle)
                time.sleep(0.04)
            motors[output_id]['state'] = False

    except Exception as e:
        log_message(f"Erro ao operar portão: {str(e)}")

def save_config():
    try:
        config = {
            'motor1_time': motors['output1']['motor'].rotation_time,
            'motor2_time': motors['output2']['motor'].rotation_time,
            'motor3_time': motors['output3']['motor'].rotation_time
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
    except Exception as e:
        log_message(f"Erro ao salvar configurações: {str(e)}")

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            motors['output1']['motor'].rotation_time = config.get('motor1_time', 5)
            motors['output2']['motor'].rotation_time = config.get('motor2_time', 5)
            motors['output3']['motor'].rotation_time = config.get('motor3_time', 5)
    except OSError:
        log_message("Arquivo de configuração não encontrado. Usando valores padrão.")
    except Exception as e:
        log_message(f"Erro ao carregar configurações: {str(e)}. Usando valores padrão.")

# Inicialização
log_message('Iniciando sistema...')
time.sleep(1)
gc.collect()

motors = {}

try:
    motor1 = StepperMotor(23, 22, 21, 19, "1", 0)
    motor2 = StepperMotor(18, 17, 16, 15, "2", 1)
    motor3 = StepperMotor(13, 12, 14, 27, "3", 2)
    log_message("Motores configurados")

    servo1 = ServoMotor(32)
    servo2 = ServoMotor(33)
    log_message("Servos configurados")

    motors = {
        'output1': {'motor': motor1, 'state': False},
        'output2': {'motor': motor2, 'state': False},
        'output3': {'motor': motor3, 'state': False},
        'output4': {'servos': [servo1, servo2], 'state': False}
    }

    load_config()
    time.sleep(0.5)

    _thread.start_new_thread(check_buttons, ())
    log_message("Sistema pronto e monitorando botões...")

except Exception as e:
    log_message(f"Erro fatal: {str(e)}")
    for motor_info in motors.values():
        if 'motor' in motor_info:
            try:
                motor_info['motor'].stop()
            except:
                pass
          