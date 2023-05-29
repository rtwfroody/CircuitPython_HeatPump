"""
Based off https://github.com/SwiCago/HeatPump
"""

import time

def hex_string(data):
	return " ".join("%02x" % c for c in data)

def checksum(bytes):
	sum = 0
	for b in bytes:
		sum += b
	return (0xfc - sum) & 0xff

class Mode:
	HEAT = 1
	DRY = 2
	COOL = 3
	FAN = 7
	AUTO = 8

class Fan:
	AUTO = 0
	QUIET = 1
	VALUE_1 = 2
	VALUE_2 = 3
	VALUE_3 = 5
	VALUE_4 = 6

class Vane:
	AUTO = 0
	VALUE_1 = 1
	VALUE_2 = 2
	VALUE_3 = 3
	VALUE_4 = 4
	VALUE_5 = 5
	SWING = 7

class Widevane:
	NONE = 0
	VALUE_FAR_LEFT = 1	# <<
	VALUE_LEFT = 2		# <
	VALUE_MIDDLE = 3	# |
	VALUE_RIGHT = 4		# >
	VALUE_FAR_RIGHT = 5	# >>
	VALUE_LEFT_RIGHT = 8	# <>
	SWING = 0xc

class InfoMode:
    RQST_PKT_SETTINGS = 2		# request a settings packet
    RQST_PKT_ROOM_TEMP = 3    # request the current room temp
    RQST_PKT_TIMERS = 5       # request the timers
    RQST_PKT_STATUS = 6		# request status -
    RQST_PKT_STANDBY = 9      # request standby mode (maybe?)

class Packet:
	HEADER = [0xfc, 0x41, 0x01, 0x30, 0x10, 0x01, 0x00, 0x00]
	LENGTH = 22

class UpdateSuccessPacket(Packet):
	pass

class ConnectSuccessPacket(Packet):
	pass

class SettingInformationPacket(Packet):
	TEMP_MAP = [31, 30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17, 16]
	def __init__(self, packet):
		self.power = bool(packet[8])
		# This iSee logic makes no sense. Is it just bit 3 that is set?
		# But then why is Mode.AUTO 8?
		self.iSee = bool(packet[9] > 0x08)
		if self.iSee:
			self.mode = packet[9] - 8
		else:
			self.mode = packet[9]

		if packet[16] != 0:
			self.temperature_c = (packet[16] - 128) / 2
			self.tempMode = True
		else:
			self.temperature_c = self.TEMP_MAP[packet[10]]
			self.tempMode = False

		self.fan = packet[11]
		self.vane = packet[12]
		self.wideVane = packet[15] & 0xf
		self.wideVaneAdj = (packet[15] & 0xf0) == 0x80

	def __str__(self):
		return (
			"SettingInformationPacket(" +
			f"power={self.power}, " +
			f"mode={self.mode}, " +
			f"temperature={self.temperature_c}, " +
			f"fan={self.fan}, " +
			f"vane={self.vane}, " +
			f"wideVane={self.wideVane}, " +
			f"wideVaneAdj={self.wideVaneAdj}, " +
			f"iSee={self.iSee}" +
			")"
		)

class SettingPacket(Packet):
	CONTROL_PACKET_1_POWER = 1
	CONTROL_PACKET_1_MODE = 2
	CONTROL_PACKET_1_TEMP = 4
	CONTROL_PACKET_1_FAN = 8
	CONTROL_PACKET_1_VANE = 0x10
	CONTROL_PACKET_2_WIDEVANE = 1

	def __init__(self, power, mode, tempMode, temperature, fan=None, vane=None, wideVane=None, wideVaneAdj=None):
		self.power = power
		self.mode = mode
		self.tempMode = tempMode
		self.temperature = temperature
		self.fan = fan
		self.vane = vane
		self.wideVane = wideVane
		self.wideVaneAdj = wideVaneAdj

	def encode_temperature(self, celsius):
		celsius = int(round(celsius))
		celsius = min(celsius, 31)
		celsius = max(celsius, 16)
		return 31 - celsius
	
	def encode(self):
		packet = self.HEADER + [0] * (Packet.LENGTH - len(self.HEADER))

		if self.power is not None:
			packet[8]  = int(self.power)
			packet[6] |= self.CONTROL_PACKET_1_POWER
		if self.mode is not None:
			packet[9]  = self.mode
			packet[6] |= self.CONTROL_PACKET_1_MODE
		if self.temperature is not None:
			packet[6] |= self.CONTROL_PACKET_1_TEMP
			if self.tempMode:
				packet[19] = int(self.temperature * 2 + 128)
			else:
				packet[10] = self.encode_temperature(self.temperature)
		if self.fan is not None:
			packet[11] = self.fan
			packet[6] |= self.CONTROL_PACKET_1_FAN
		if self.vane is not None:
			packet[12] = self.vane
			packet[6] += self.CONTROL_PACKET_1_VANE
		if self.wideVane is not None:
			assert(self.wideVaneAdj is not None)
			packet[18] = self.wideVane | self.wideVaneAdj
			packet[7] += self.CONTROL_PACKET_2_WIDEVANE
		# This works because byte 21 is 0, and the checksum is simple.
		packet[21] = checksum(packet)

		return bytes(packet)

	def __str__(self):
		return (
			"SettingPacket(" +
			f"power={self.power}, " +
			f"mode={self.mode}, " +
			f"tempMode={self.tempMode}, " +
			f"temperature={self.temperature}, " +
			f"fan={self.fan}, " +
			f"vane={self.vane}, " +
			f"wideVane={self.wideVane}, " +
			f"wideVaneAdj={self.wideVaneAdj}" +
			")"
		)

class TemperaturePacket(Packet):
	def __init__(self, temperature_c):
		self.temperature_c = temperature_c
		
	def encode(self):
		packet = self.HEADER + [0] * (Packet.LENGTH - len(self.HEADER))
		packet[5] = 7
		if self.temperature_c > 0:
			packet[6] = 1
			value = round(self.temperature_c * 2) / 2
			temp1 = 3 + ((value - 10) * 2);
			packet[7] = int(temp1)
			temp2 = (value * 2) + 128;
			packet[8] = int(temp2)
		else:
			packet[6] = 0
			packet[8] = 0x80

		packet[21] = checksum(packet)

		return bytes(packet)

	def __str__(self):
		return f"TemperaturePacket({self.temperature_c})"

class InfoRequestPacket(Packet):
	"""Packet to request information from the heatpump."""

	INFOHEADER = [0xfc, 0x42, 0x01, 0x30, 0x10]

	def __init__(self, infoMode):
		self.infoMode = infoMode

	def encode(self):
		packet = self.INFOHEADER + [0] * (Packet.LENGTH - len(self.INFOHEADER))
		packet[5] = self.infoMode
		packet[21] = checksum(packet)
		return bytes(packet)

	def __str__(self):
		return f"InfoRequestPacket({self.infoMode})"

class StatusPacket(Packet):
	def __init__(self, packet=None):
		if packet:
			self.compressorFrequency = packet[8]
			self.operating = packet[9]
		else:
			self.compressorFrequency = 0
			self.operating = 0

	def __str__(self):
		return (
			"StatusPacket(" +
			f"compressorFrequency={self.compressorFrequency}, " +
			f"operating={self.operating}"
			")"
		)

class RoomTemperaturePacket(Packet):
	def __init__(self, packet):
		if packet[11] != 0:
			self.temperature_c = (packet[16] - 128) / 2
		else:
			self.temperature_c = self.TEMP_MAP[packet[8]]

	def __str__(self):
		return f"RoomTemperaturePacket({self.temperature_c})"

class ConnectPacket(Packet):
	def encode(self):
		return b'\xfc\x5a\x01\x30\x02\xca\x01\xa8'

class HeatPump:
	PACKET_LEN = 22

	def debug(self, *args):
		if self.log:
			self.log.debug(*args)
		else:
			print(*args)

	def __init__(self, serial, log=None):
		self.serial = serial
		self.log = log

		# True/False
		self.power = False
		# "HEAT", "DRY", "COOL", "FAN", "AUTO"
		self.mode = Mode.HEAT
		self.temperature_c = 20
		self.remote_temperature_c = 20
		# "AUTO", "QUIET", "1", "2", "3", "4"
		self.fan = Fan.AUTO
		# "AUTO", "1", "2", "3", "4", "5", "SWING"
		self.vane = Vane.AUTO # vertical vane, up/down
		# "<<", "<",  "|",  ">",  ">>", "<>", "SWING"
		self.wideVane = Widevane.NONE
		self.iSee = False  # iSee sensor, at the moment can only detect it, not set it

		self.tempMode = False
		# Value gets ORed into widevane byte.
		self.wideVaneAdj = 0

		self.send_buffer = ""
		self.receive_buffer = []
		self.last_sent = 0
		self.last_received = 0
		self.packet_cycle = 0
		# Last SettingInformationPacket received from the heatpump.
		self.last_information = None

		self.status = StatusPacket()

	def set_power(self, value : bool):
		self.power = value

	def set_mode(self, value):
		self.mode = value

	def set_fan(self, value):
		self.fan = value

	def set_vane(self, value):
		self.vane = value

	def set_temperature_c(self, value : float):
		self.temperature_c = value

	def send(self, packet : Packet):
		self.debug("Sending to heatpump:", packet)
		assert(not self.send_buffer)
		self.send_buffer = packet.encode()

	def connect(self):
		self.send(ConnectPacket())
	
	def connected(self):
		return time.monotonic() - self.last_received < 60

	def send_setting(self):
		if (not self.last_information or
				self.power != self.last_information.power or
				self.mode != self.last_information.mode or
				abs(self.temperature_c - self.last_information.temperature_c) > 0.01 or
				self.fan != self.last_information.fan or
				self.vane != self.last_information.vane or
				self.wideVane != self.last_information.wideVane):
			self.send(SettingPacket(self.power, self.mode, self.tempMode,
				self.temperature_c, self.fan, self.vane, self.wideVane,
				self.wideVaneAdj))
		else:
			self.debug("No need to send setting again.")

	def send_remote_temperature(self):
		self.send(TemperaturePacket(self.remote_temperature_c))

	def poll(self):
		data = self.serial.read(32)
		if data:
			#self.debug(time.monotonic(), "received:", hex_string(data))
			self.last_received = time.monotonic()
			self.receive_buffer += data
		packet = self.find_packet()
		if packet:
			decoded_packet = self.decode_packet(packet)
			if isinstance(decoded_packet, SettingInformationPacket):
				self.last_information = decoded_packet
				self.tempMode = decoded_packet.tempMode
			elif isinstance(decoded_packet, StatusPacket):
				self.status = decoded_packet
			self.debug("received:", decoded_packet)
			return

		if self.send_buffer:
			l = len(self.send_buffer)
			data = self.send_buffer[:l]
			#self.debug(time.monotonic(), "sending:", hex_string(data))
			self.serial.write(data)
			self.send_buffer = self.send_buffer[l:]
			self.last_sent = time.monotonic()
			return

		now = time.monotonic() 

		if not self.connected():
			if now - self.last_sent >= 20:
				self.connect()
			return

		if now - self.last_sent >= 5:
			choice = self.packet_cycle % 6
			self.packet_cycle += 1
			if choice == 0:
				self.send_setting()
			#elif choice == 1:
			#	self.send_remote_temperature()
			elif choice == 2:
				self.send(InfoRequestPacket(InfoMode.RQST_PKT_SETTINGS))
			elif choice == 3:
				self.send(InfoRequestPacket(InfoMode.RQST_PKT_ROOM_TEMP))
			elif choice == 4:
				self.send(InfoRequestPacket(InfoMode.RQST_PKT_TIMERS))
			elif choice == 5:
				self.send(InfoRequestPacket(InfoMode.RQST_PKT_STATUS))

	def decode_packet(self, packet):
		if packet[1] == 0x62:
			if packet[5] == 2:
				p = SettingInformationPacket(packet)
				self.wideVaneAdj = p.wideVaneAdj
				return p
			elif packet[5] == 3:
				return RoomTemperaturePacket(packet)
			elif packet[5] == 6:
				return StatusPacket(packet)
			else:
				self.debug(f"Unsupported data packet type {packet[5]}")
		elif packet[1] == 0x61:
			# Last update was successful
			return UpdateSuccessPacket()
		elif packet[1] == 0x7a:
			self._connected = True
			return ConnectSuccessPacket()

	def find_packet(self):
		# Look for a valid header
		def rb():
			return self.receive_buffer
		def rbl():
			return len(self.receive_buffer)

		while (rbl() > 0 and rb()[0] != Packet.HEADER[0]) or \
				(rbl() > 2 and rb()[2] != Packet.HEADER[2]) or \
				(rbl() > 3 and rb()[3] != Packet.HEADER[3]):
			self.receive_buffer = self.receive_buffer[1:]

		if len(self.receive_buffer) < 5:
			return
		data_length = self.receive_buffer[4]
		packet_length = 5 + data_length + 1
		if len(self.receive_buffer) < packet_length:
			return
		packet = self.receive_buffer[:packet_length]
		self.receive_buffer = self.receive_buffer[packet_length:]

		# Packet consists of a 5-byte header, the data, and a 1-byte checksum
		sum = checksum(packet[:-1])
		if sum != packet[-1]:
			self._connected = False
			return
		
		return packet

	def set_remote_temperature_c(self, temperature_c):
		self.remote_temperature_c = temperature_c
