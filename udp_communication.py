import socket
import struct
import time
import math
import binascii
import os


def utf8len(string):
    return len(string.encode('utf-8'))

# Funkcia na výpočet CRC
def crc32(v):
    checksum = binascii.crc32(v)
    return checksum

# Funkcia pre odpočítavanie sekúnd - používa sa pri keepalive
def countdown(t):
    while t:
        time.sleep(1)
        t -= 1


while True:
    # Vytvorenie socketu
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Používateľ si môže vybrať, či bude mať rolu Server alebo Client
    rola = input("Server/Client: ")

    port = ""
    if rola == 'Server':

        port = input("Zadaj port: ")

        # Zaviazanie sa na zadaný port
        sock.bind(('', int(port)))

        # Kam bude chcieť používateľ uložiť všetky súbory, ktoré môžu byť poslané od klienta
        cesta = input("Zadaj, kam budeš chcieť uložiť súbory: ")
        while True:

            prijate_fragmenty = 0
            prijate_list = []
            packet = b""
            subor = ""
            sprava = ""
            fin = 0
            while True:
                # Prijatie fragmentov
                data, clientaddr = sock.recvfrom(65535)
                header = data[:12]   # hlavička má veľkosť 12B
                data = data[12:]
                # Hlavička
                (typ, pocet_fragment, index_fragment, velkost_fragment, crc) = struct.unpack('!hhhhI', header)

                # Výpis s informáciami o fragmente
                print("%d. fragment veľkosti %d" % (index_fragment, velkost_fragment))
                print("Typ: " + str(typ) +
                    "\nPočet fragmentov: " + str(pocet_fragment) +
                    "\nIndex fragmentu: " + str(index_fragment) +
                    "\nVeľkosť fragmentu: " + str(velkost_fragment) +
                    "\nCRC: " + str(crc) + "\nCRC DATA: " + str(crc32(data)))

                # Ak sa prijaté CRC zhoduje s vypočítaným CRC nad dátami
                index_ack = 0
                index_nack = 0
                if crc == crc32(data):
                    typ_ack_nack = 4
                    pocet_fragment_ack = 1
                    index_ack += 1
                    data_ack = bytes("ACK", 'utf-8')
                    velkost_fragment_ack = len(data_ack)
                    header = struct.pack('!hhhhI', typ_ack_nack, pocet_fragment_ack, index_ack, velkost_fragment_ack, crc32(data_ack))
                    sock.sendto(header + data_ack, clientaddr)  # pošli ACK

                    # Ak je typ fragmentu správa
                    if typ == 1:
                        prijate_list.append(data.decode())
                        sprava = ''.join(prijate_list)
                        print(data.decode())

                    # Súbor má označenie 2 - ako prvý fragment príde názov súboru
                    elif typ == 2 and prijate_fragmenty == 0:
                        subor = data.decode()

                    # Vytvorenie a zápis dát do nového súboru
                    elif typ == 2 and prijate_fragmenty != 0:
                        packet += data
                        f = open(cesta + subor, 'wb')
                        f.write(packet)

                    # Keepalive
                    elif typ == 3:
                        print(data.decode() + "\n")
                        if data.decode() == "Ukončujem spojenie..":
                            fin = 1

                    prijate_fragmenty += 1

                else:
                    typ_ack_nack = 4
                    pocet_fragment_nack = 1
                    index_nack += 1
                    data_nack = bytes("NACK", 'utf-8')
                    velkost_fragment_nack = len(data_nack)
                    header = struct.pack('!hhhhI', typ_ack_nack, pocet_fragment_nack, index_nack, velkost_fragment_nack, crc32(data_nack))
                    sock.sendto(header + data_nack, clientaddr)  # pošli NACK

                # Ak prišli všetky fragmenty - skonči
                if prijate_fragmenty == pocet_fragment:
                    break

            if typ == 2:
                print("Súbor bol uložený v " + os.path.abspath(subor))  # Vypíše cestu súboru
            elif typ == 1:
                print("Správa: %s" % sprava)        # Vypíše kompletnú správu

            # Ukončenie spojenia
            if fin == 1:
                print("Spojenie bolo ukončené!\n")
                sock.close()
                break

            print("\nČakám na klienta...\n")

    elif rola == 'Client':

        # Inicializačné nastavenie - IP a PORT
        serverip = input("Zadaj IP, kam budeš chcieť poslať správu alebo súbor: ")
        serverport = int(input("Zadaj PORT: "))

        # Pripojenie na server
        sock.connect((serverip, serverport))
        sock.settimeout(2)
        while True:
            print("Zadaj, čo chceš poslať: \n(1) správa \n(2) súbor")
            typ = int(input())
            celkova_velkost = 0
            pocet_fragment = 0
            max_fragment = int(input("Zadaj max veľkosť fragmentu: "))

            # Poslanie správy
            if typ == 1:

                sprava = input("Zadaj správu: ")
                pocet_fragment = math.ceil(utf8len(sprava) / max_fragment)
                index_fragment = 0

                while sprava:

                    data = bytearray()
                    data.extend(bytes(sprava[:max_fragment], 'utf-8'))
                    index_fragment += 1

                    velkost_fragment = utf8len(sprava[:max_fragment])

                    # Hlavička
                    header = struct.pack('!hhhhI', typ, pocet_fragment, index_fragment, velkost_fragment, crc32(data))
                    sock.sendto(header + data, (serverip, serverport))   # poslanie hlavičky s dátami na server

                    celkova_velkost += velkost_fragment + len(header)

                    print("Posielam %d. fragment veľkosti %d" % (index_fragment, velkost_fragment))

                    sprava = sprava[max_fragment:]

                    # Odpoveď od serveru
                    odpoved, addr = sock.recvfrom(65535)
                    header = odpoved[:12]  # hlavička má veľkosť 12B
                    odpoved = odpoved[12:]
                    # Hlavička
                    (typ_odpoved, pocet_fragment_odpoved, index_odpoved, velkost_fragment_odpoved, crc_odpoved) = struct.unpack('!hhhhI', header)
                    print("Odpoveď: %s" % odpoved.decode())
                    celkova_velkost += len(odpoved) + len(header)
                    # Ak bol fragment chybný, teda prišlo NACK
                    if odpoved.decode() == 'NACK':
                        counter = 0
                        # Posielam kým nepríde ACK alebo poslal som už daný fragment 3x
                        while counter <= 3:
                            crc = crc32(data)  # znova vypočítam CRC
                            header = struct.pack('!hhhhI', typ, pocet_fragment, index_fragment, velkost_fragment, crc)
                            sock.sendto(header + data, (serverip, serverport))    # znova sa pošle daný fragment
                            print("Znovu posielam %d. fragment veľkosti %d" % (index_fragment, velkost_fragment))

                            odpoved, addr = sock.recvfrom(65535)  # Znova počkám na odpoveď
                            header = odpoved[:12]
                            odpoved = odpoved[12:]
                            # Hlavička
                            (typ_odpoved, pocet_fragment_odpoved, index_odpoved, velkost_fragment_odpoved, crc_odpoved) = struct.unpack('!hhhhI', header)
                            print("Odpoveď: %s" % odpoved.decode())
                            celkova_velkost += len(odpoved) + len(header)
                            counter += 1
                            if odpoved.decode() == "ACK":
                                break

            # Poslanie súboru
            elif typ == 2:

                subor_input = input("Zadaj cestu a meno súboru: ")
                nazov_suboru = subor_input.split('\\')[-1:]    # názov súboru sa nachádza v ceste na poslednom mieste - rozdelím cestu podľa \
                f = open(subor_input, "rb")   # otvorím súbor a prečítam ho naraz v bajtoch
                contents = f.read()

                nazov_suboru = str(nazov_suboru[0])
                pocet_fragment = math.ceil(len(contents) / max_fragment) + 1
                index_fragment = 1
                celkova_velkost = 0
                velkost_fragment = len(nazov_suboru)

                simulacia_chyby = input("Chceš simulovať chybu? (1 - áno / 2 - nie) ")    # simulácia chyby
                print("Posielam súbor %s..." % nazov_suboru)

                # Najskôr pošlem názov súboru v samostatnom fragmente
                subor = bytearray()
                subor.extend(bytes(nazov_suboru, 'utf-8'))

                header = struct.pack('!hhhhI', typ, pocet_fragment, index_fragment, velkost_fragment, crc32(subor))
                sock.sendto(header + subor, (serverip, serverport))
                print("Posielam %d. fragment veľkosti %d" % (index_fragment, velkost_fragment))
                celkova_velkost += velkost_fragment + len(header)

                odpoved, addr = sock.recvfrom(65535)
                header = odpoved[:12]  # hlavička má veľkosť 12B
                odpoved = odpoved[12:]
                # Hlavička
                (typ_odpoved, pocet_fragment_odpoved, index_odpoved, velkost_fragment_odpoved, crc_odpoved) = struct.unpack('!hhhhI', header)
                print("Odpoveď: %s" % odpoved.decode())
                celkova_velkost += len(odpoved) + len(header)

                while contents:

                    data = bytearray()
                    data.extend(contents[:max_fragment])
                    index_fragment += 1
                    velkost_fragment = len(contents[:max_fragment])

                    if simulacia_chyby == "1" and index_fragment % 5 == 0:
                        crc = 1111111    # pri simulácii chyby natvrdo zmením crc fragmentu
                    else:
                        crc = crc32(data)

                    # Hlavička
                    header = struct.pack('!hhhhI', typ, pocet_fragment, index_fragment, velkost_fragment, crc)
                    sock.sendto(header + data, (serverip, serverport))

                    celkova_velkost += velkost_fragment + len(header)

                    print("Posielam %d. fragment veľkosti %d" % (index_fragment, velkost_fragment))

                    print("crc: " + str(crc))

                    contents = contents[max_fragment:]

                    # Odpoveď
                    odpoved, addr = sock.recvfrom(65535)
                    header = odpoved[:12]  # hlavička má veľkosť 12B
                    odpoved = odpoved[12:]
                    # Hlavička
                    (typ_odpoved, pocet_fragment_odpoved, index_odpoved, velkost_fragment_odpoved, crc_odpoved) = struct.unpack('!hhhhI', header)
                    print("Odpoveď: %s" % odpoved.decode())
                    celkova_velkost += len(odpoved) + len(header)
                    if odpoved.decode() == 'NACK':
                        counter = 0
                        # Posielam kým nepríde ACK alebo poslal som už daný fragment 3x
                        while counter <= 3:
                            crc = crc32(data)
                            header = struct.pack('!hhhhI', typ, pocet_fragment, index_fragment, velkost_fragment, crc)
                            sock.sendto(header + data, (serverip, serverport))
                            print("Znovu posielam %d. fragment veľkosti %d" % (index_fragment, velkost_fragment))
                            print("crc: " + str(crc))

                            odpoved, addr = sock.recvfrom(65535)
                            header = odpoved[:12]  # hlavička má veľkosť 12B
                            odpoved = odpoved[12:]
                            # Hlavička
                            (typ_odpoved, pocet_fragment_odpoved, index_odpoved, velkost_fragment_odpoved, crc_odpoved) = struct.unpack('!hhhhI', header)
                            print("Odpoveď: %s" % odpoved.decode())
                            celkova_velkost += len(odpoved) + len(header)
                            counter += 1
                            if odpoved.decode() == "ACK":
                                break

                print("\nSúbor bol odoslaný.")

            print(serverip, serverport, max_fragment, pocet_fragment, "Celková veľkosť odoslaných správ: %d" % celkova_velkost)

            index_fragment = 1
            nack_counter = 0
            # Keepalive - každých 15 sekúnd sa pošle správa na server, kým to používateľ neukončí
            while True:
                try:
                    countdown(15)
                    typ = 3
                    pocet_fragment = 1
                    print("Posielam keepalive... pre ukončenie stlač ctrl+c")
                    data = bytes("Udržujem spojenie..", 'utf-8')
                    crc = crc32(data)
                    velkost_fragment = len(data)
                    header = struct.pack('!hhhhI', typ, pocet_fragment, index_fragment, velkost_fragment, crc)
                    sock.sendto(header + data, (serverip, serverport))
                    index_fragment += 1
                    try:
                        odpoved, addr = sock.recvfrom(65535)
                        header = odpoved[:12]  # hlavička má veľkosť 12B
                        odpoved = odpoved[12:]
                        # Hlavička
                        (typ_odpoved, pocet_fragment_odpoved, index_odpoved, velkost_fragment_odpoved, crc_odpoved) = struct.unpack('!hhhhI', header)
                        print("Odpoveď: %s" % odpoved.decode())
                    except Exception as e:              # server neodpovedá
                        odpoved = "NACK"
                        print("Odpoveď: %s" % odpoved)

                    if odpoved == "NACK":
                        nack_counter += 1
                    else:
                        nack_counter = 0

                    if nack_counter == 3:           # keď bude NACK 3x po sebe -> koniec
                        print("Server neodpovedá.. Ukončujem posielanie keepalive.")
                        break
                except KeyboardInterrupt:
                    break

            # Ukončenie spojenia so serverom
            koniec_spojenia = input("Chceš ukončiť spojenie so serverom? Y/n ")
            if koniec_spojenia == "Y":
                typ = 3
                pocet_fragment = 1
                data = bytes("Ukončujem spojenie..", 'utf-8')
                crc = crc32(data)
                velkost_fragment = len(data)
                index_fragment = 1
                header = struct.pack('!hhhhI', typ, pocet_fragment, index_fragment, velkost_fragment, crc)
                sock.sendto(header + data, (serverip, serverport))
                sock.close()
                break