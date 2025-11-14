import math

# --- Struktur Data (Representasi Data Pabrik) ---

# FACTORY_RESOURCES: Informasi statis tentang mesin dan operator
# - speed_m_per_min: kecepatan dalam meter/menit
# - speed_sec_per_bend: kecepatan dalam detik/tekukan
# - power_kw: daya dalam kiloWatt
# - units: jumlah unit mesin yang tersedia (0 jika ini hanya peran proses/operator, bukan unit jadwal mandiri)
# - operators_needed: jumlah operator yang dibutuhkan per unit mesin saat beroperasi
FACTORY_RESOURCES = {
    "machines": {
        "Yane600": {"speed_m_per_min": 16, "power_kw": 11, "units": 2, "operators_needed": 1}, # Data mesin Yane600 [cite: image_e11b6a, revisi operator]
        "Yane672": {"speed_m_per_min": 20, "power_kw": 16.5, "units": 1, "operators_needed": 1}, # Data mesin Yane672 (rata-rata kecepatan 20m/menit) [cite: image_e11b6a, revisi operator]
        "Yane750": {"speed_m_per_min": 20, "power_kw": 9.5, "units": 1, "operators_needed": 1}, # Data mesin Yane750 (rata-rata kecepatan 20m/menit) [cite: image_e11b6a, revisi operator]
        "Bending": {"speed_sec_per_bend": 4, "power_kw": 9.7, "units": 2, "operators_needed": 2}, # Data mesin Bending (rata-rata 4 detik/tekukan, 9.7kW hasil konversi) [cite: image_e11b6a, konversi daya]
        "Shearing": {"units": 0, "operators_needed": 2}, # Ditambahkan 'units': 0 karena ini peran proses/operator, bukan mesin schedulable mandiri. [FIX]
        "Forklift": {"units": 0, "operators_needed": 1}  # Ditambahkan 'units': 0 karena ini peran proses/operator, bukan mesin schedulable mandiri. [FIX]
    },
    "total_operators_pool": 10, # Total operator yang tersedia di pabrik [cite: sebelumnya]
    "daily_work_minutes": 8 * 60, # 8 jam/hari = 480 menit/hari [cite: sebelumnya]
    "work_days_per_week": 5     # Asumsi Sabtu Minggu libur [cite: sebelumnya]
}

# Inisialisasi Status Pabrik (akan diupdate seiring penjadwalan)
# machine_schedules: Melacak slot waktu yang ditempati pada setiap unit mesin per hari
#    Format: { 'MesinID_UnitNum': { 'Day X': [ (start_minute, end_minute, 'OrderID') ] } }
# operator_daily_load: Melacak total operator yang sudah dialokasikan untuk setiap hari
#    Format: { 'Day X': jumlah_operator_dialokasikan }
# production_log: Daftar hasil penjadwalan setiap pesanan
machine_schedules = {}
for machine_name, data in FACTORY_RESOURCES["machines"].items():
    if data["units"] > 0: # Hanya inisialisasi jika mesin memiliki unit yang dapat dijadwalkan [FIX]
        for i in range(data["units"]):
            machine_schedules[f"{machine_name}_{i+1}"] = {}

operator_daily_load = {}
production_log = []

# --- Algoritma Perhitungan Waktu dan Daya ---

def calculate_etc_forming(total_length_m, machine_speed_m_per_min):
    """
    Menghitung Estimasi Waktu Penyelesaian (ETC) untuk proses Forming dalam menit.
    ETC_Forming (menit) = Total Panjang Pesanan (meter) / Kecepatan Mesin Forming (meter/menit)
    """
    if machine_speed_m_per_min <= 0:
        return float('inf') # Menghindari pembagian nol atau kecepatan tidak valid
    return total_length_m / machine_speed_m_per_min

def calculate_etc_bending(total_bends, machine_speed_sec_per_bend=4):
    """
    Menghitung Estimasi Waktu Penyelesaian (ETC) untuk proses Bending dalam menit.
    ETC_Bending (menit) = Total Jumlah Tekukan * Waktu per Tekukan (detik) / 60 detik/menit
    """
    if machine_speed_sec_per_bend <= 0:
        return float('inf') # Menghindari pembagian nol atau kecepatan tidak valid
    return (total_bends * machine_speed_sec_per_bend) / 60

def calculate_power_consumption(machine_power_kw, etc_minutes):
    """
    Menghitung konsumsi daya dalam kilowatt-hour (kWh).
    Konsumsi_Daya (kWh) = Daya Mesin (kW) * (ETC (menit) / 60 menit/jam)
    """
    if etc_minutes < 0:
        return 0
    return machine_power_kw * (etc_minutes / 60)

# --- Langkah-langkah Algoritma ---

def get_next_available_slot(machine_id, required_minutes, current_day):
    """
    Mencari slot waktu tersedia pertama pada sebuah unit mesin di hari tertentu.
    Mengembalikan (start_time_minutes, end_time_minutes) atau (None, None) jika tidak tersedia.
    """
    daily_schedule = machine_schedules[machine_id].get(current_day, [])
    daily_schedule.sort(key=lambda x: x[0]) # Pastikan jadwal terurut berdasarkan waktu mulai

    # Cari slot di antara tugas yang ada atau setelah tugas terakhir
    last_end_time = 0
    for start, end, _ in daily_schedule:
        # Cek slot di antara tugas
        if (start - last_end_time) >= required_minutes:
            return last_end_time, last_end_time + required_minutes
        last_end_time = max(last_end_time, end) # Pastikan last_end_time selalu maju

    # Cek slot setelah tugas terakhir hingga akhir jam kerja
    if (FACTORY_RESOURCES["daily_work_minutes"] - last_end_time) >= required_minutes:
        return last_end_time, last_end_time + required_minutes
    
    return None, None # Tidak ada slot yang tersedia

def select_best_machine_unit(machine_type_prefix, required_minutes, current_day):
    """
    Memilih unit mesin terbaik (paling awal tersedia) dari jenis tertentu.
    Jika ada banyak unit (misal Yane600_1, Yane600_2), pilih yang paling cocok.
    """
    best_unit_id = None
    earliest_start_time = FACTORY_RESOURCES["daily_work_minutes"] + 1 # Inisialisasi dengan waktu yang mustahil
    
    # Iterate through all units of the given machine type
    for unit_id in machine_schedules.keys():
        if unit_id.startswith(machine_type_prefix):
            start_time, _ = get_next_available_slot(unit_id, required_minutes, current_day)
            
            if start_time is not None:
                if start_time < earliest_start_time:
                    earliest_start_time = start_time
                    best_unit_id = unit_id
    
    if best_unit_id:
        return best_unit_id, earliest_start_time
    return None, None


def check_and_assign_operators(required_operators, current_day):
    """
    Memeriksa ketersediaan operator dari pool dan mengalokasikannya untuk tugas.
    Mengembalikan True jika operator tersedia, False jika tidak.
    """
    current_allocated = operator_daily_load.get(current_day, 0)
    
    if (FACTORY_RESOURCES["total_operators_pool"] - current_allocated) >= required_operators:
        # Asumsi: Karena operator multifungsi dan akan "dialokasikan" ke tugas
        # kita hanya perlu memastikan total pool tidak terlampaui untuk pekerjaan simultan
        return True
    return False

def allocate_operators(required_operators, current_day):
    """Mengupdate jumlah operator yang dialokasikan untuk hari tersebut."""
    operator_daily_load[current_day] = operator_daily_load.get(current_day, 0) + required_operators

def schedule_order(order, machine_id, start_time_minutes, etc_minutes, operators_needed):
    """Menambahkan pesanan ke jadwal mesin dan log produksi."""
    end_time_minutes = start_time_minutes + etc_minutes
    
    # Update jadwal mesin
    if order["order_id"] not in [item[2] for item in machine_schedules[machine_id].get(current_date_str, [])]: # avoid duplicates
         if current_date_str not in machine_schedules[machine_id]:
             machine_schedules[machine_id][current_date_str] = []
         machine_schedules[machine_id][current_date_str].append((start_time_minutes, end_time_minutes, order["order_id"]))
         # Sort to maintain ascending order for next scheduling check
         machine_schedules[machine_id][current_date_str].sort(key=lambda x: x[0])

    # Update ketersediaan operator sudah dilakukan di fungsi pemanggil (run_production_scheduling_algorithm)
    # melalui allocate_operators()

    # Hitung konsumsi daya
    # Dapatkan power_kw dari nama mesin (misal 'Yane600_1' -> 'Yane600')
    machine_base_name = machine_id.split('_')[0]
    power_consumed = calculate_power_consumption(FACTORY_RESOURCES["machines"][machine_base_name]["power_kw"], etc_minutes)

    # Catat dalam log produksi
    production_log.append({
        "order_id": order["order_id"],
        "product_type": order["product_type"],
        "assigned_machine": machine_id,
        "start_time_minutes": start_time_minutes,
        "end_time_minutes": end_time_minutes,
        "duration_minutes": etc_minutes,
        "operators_assigned": operators_needed,
        "power_consumption_kWh": power_consumed,
        "scheduled_date": current_date_str # Menggunakan current_date_str global
    })
    print(f"  > Order {order['order_id']} ({order['product_type']}) dijadwalkan pada {machine_id} dari menit {start_time_minutes} hingga {end_time_minutes}.")


def run_production_scheduling_algorithm(orders_queue):
    """
    Fungsi utama untuk menjalankan algoritma penjadwalan produksi.
    Memproses pesanan berdasarkan pohon keputusan dan mencatat alur produksi.
    """
    global current_date_str # Deklarasikan sebagai global untuk diupdate di dalam fungsi
    
    current_day_num = 1
    current_date_str = f"Day {current_day_num}" # Inisialisasi awal

    # Loop hingga semua pesanan terjadwal
    while True:
        # Identifikasi pesanan yang belum terjadwal
        pending_orders = [order for order in orders_queue if not order.get("is_scheduled", False)]
        
        if not pending_orders:
            print("\n--- Semua pesanan telah berhasil dijadwalkan. ---")
            break # Keluar dari loop jika semua pesanan terjadwal

        print(f"\n--- Memproses penjadwalan untuk {current_date_str} ---")
        
        # Reset beban operator untuk hari baru jika ini hari pertama atau hari baru
        if current_date_str not in operator_daily_load:
            operator_daily_load[current_date_str] = 0

        # Prioritaskan pesanan: Mendesak terlebih dahulu, kemudian berdasarkan ID untuk konsistensi
        pending_orders.sort(key=lambda x: (1 if x["priority"] == "Mendesak" else 2, x["order_id"]))
        
        # Flag untuk mengecek apakah ada pesanan yang berhasil dijadwalkan di hari ini
        scheduled_in_current_day_iteration = False # Mengganti nama agar tidak konflik dengan global scheduled_in_current_day

        for order in pending_orders:
            # Jika pesanan ini sudah dijadwalkan oleh iterasi sebelumnya di hari ini, lewati
            if order.get("is_scheduled", False):
                continue

            machine_type_prefix = None
            etc_minutes = 0
            required_operators_for_task = 0 # Operator yang dibutuhkan untuk tugas spesifik ini

            print(f"  Mencoba menjadwalkan Order {order['order_id']} ({order['product_type']})")

            # --- Node 1: Klasifikasi Alur Kerja (Forming vs. Shearing & Bending) ---
            if order["product_type"] in ["Yane600", "Yane672", "Yane750", "SD680", "Kabe325"]:
                workflow_type = "FORMING"
                # --- Node 2.1 (Forming): Identifikasi Mesin & Perhitungan ETC ---
                # Asumsi SD680 dan Kabe325 diproduksi di mesin forming yang ada, misalnya Yane750
                if order["product_type"] in ["SD680", "Kabe325"]:
                    machine_type_prefix = "Yane750"
                else:
                    machine_type_prefix = order["product_type"]
                
                machine_data = FACTORY_RESOURCES["machines"].get(machine_type_prefix)
                if not machine_data:
                    print(f"    ERROR: Mesin untuk {order['product_type']} tidak teridentifikasi dalam data sumber daya.")
                    continue

                etc_minutes = calculate_etc_forming(order["total_length_m"], machine_data["speed_m_per_min"])
                required_operators_for_task = machine_data["operators_needed"]
                
                print(f"    -> Workflow: {workflow_type}. Mesin: {machine_type_prefix}. ETC: {etc_minutes:.2f} menit. Operator dibutuhkan: {required_operators_for_task}.")
                
                # --- Node 4: Pengecekan Ketersediaan Mesin ---
                assigned_machine_id, start_time = select_best_machine_unit(machine_type_prefix, etc_minutes, current_date_str)
                
                if assigned_machine_id:
                    # --- Node 5: Pengecekan Ketersediaan Operator ---
                    # Periksa apakah total operator yang akan dialokasikan (termasuk tugas ini) tidak melebihi pool
                    if check_and_assign_operators(required_operators_for_task, current_date_str):
                        # Semua sumber daya tersedia, jadwalkan!
                        schedule_order(order, assigned_machine_id, start_time, etc_minutes, required_operators_for_task)
                        order["is_scheduled"] = True
                        allocate_operators(required_operators_for_task, current_date_str) # Tandai operator sudah dialokasikan
                        scheduled_in_current_day_iteration = True
                    else:
                        print(f"    Tidak cukup operator tersedia untuk Order {order['order_id']} pada {current_date_str}.")
                        # Lanjut ke penanganan konflik (atau coba lagi nanti)
                else:
                    print(f"    Mesin {machine_type_prefix} tidak tersedia untuk Order {order['order_id']} pada {current_date_str}.")
                    # Lanjut ke penanganan konflik
                    
            elif order["product_type"] == "Aksesoris":
                workflow_type = "SHEARING_BENDING"
                # --- Node 3 (Shearing & Bending): Perhitungan Total Tekukan & ETC ---
                total_bends = order["bends_per_accessory"] * order["num_accessories"]
                etc_minutes = calculate_etc_bending(total_bends)
                
                # Total operator untuk tim S&B yang beroperasi simultan (Shearing + Forklift + Bending)
                # Asumsi 1 tim S&B untuk 1 pesanan Aksesoris
                required_operators_for_task = FACTORY_RESOURCES["machines"]["Shearing"]["operators_needed"] + \
                                               FACTORY_RESOURCES["machines"]["Forklift"]["operators_needed"] + \
                                               FACTORY_RESOURCES["machines"]["Bending"]["operators_needed"] # Untuk 1 unit Bending
                                               
                print(f"    -> Workflow: {workflow_type}. Total Tekukan: {total_bends}. ETC: {etc_minutes:.2f} menit. Operator dibutuhkan: {required_operators_for_task}.")

                # --- Node 4: Pengecekan Ketersediaan Mesin (Bending sebagai representasi lini S&B) ---
                assigned_machine_id, start_time = select_best_machine_unit("Bending", etc_minutes, current_date_str)
                
                if assigned_machine_id:
                    # --- Node 5: Pengecekan Ketersediaan Operator ---
                    if check_and_assign_operators(required_operators_for_task, current_date_str):
                        # Semua sumber daya tersedia, jadwalkan!
                        schedule_order(order, assigned_machine_id, start_time, etc_minutes, required_operators_for_task)
                        order["is_scheduled"] = True
                        allocate_operators(required_operators_for_task, current_date_str) # Tandai operator sudah dialokasikan
                        scheduled_in_current_day_iteration = True
                    else:
                        print(f"    Tidak cukup operator tersedia untuk Order {order['order_id']} pada {current_date_str}.")
                        # Lanjut ke penanganan konflik
                else:
                    print(f"    Mesin Bending tidak tersedia untuk Order {order['order_id']} pada {current_date_str}.")
                    # Lanjut ke penanganan konflik
            else:
                print(f"    ERROR: Tipe produk tidak dikenal: {order['product_type']}.")
                order["is_scheduled"] = False # Tandai sebagai tidak terjadwal
                continue # Lanjut ke pesanan berikutnya

            # --- Node 6: Penanganan Konflik (jika tidak berhasil dijadwalkan di atas) ---
            if not order.get("is_scheduled", False):
                print(f"    Menangani konflik untuk Order {order['order_id']} (Prioritas: {order['priority']}).")
                # Jika pesanan prioritas tinggi (Mendesak) tidak bisa dijadwalkan hari ini,
                # dalam implementasi nyata bisa ada logika untuk preemptive atau mencari slot malam
                # Untuk pseudo-code ini, akan dijadwalkan ulang ke hari berikutnya.
                if order["priority"] == "Mendesak":
                    print(f"      -> Order {order['order_id']} mendesak, akan dicoba jadwalkan di hari kerja berikutnya.")
                else:
                    print(f"      -> Order {order['order_id']} akan dijadwalkan ulang ke hari kerja berikutnya.")
                # Penting: order["is_scheduled"] tetap False agar bisa dicoba lagi di hari berikutnya
                # Tapi untuk tujuan demo ini, kita akan menandainya agar tidak terus-menerus mencoba di hari yang sama
                # Dalam algoritma nyata, ini akan dipindahkan ke daftar 'pending untuk hari berikutnya' agar tidak terus diiterasi di hari yang sama jika resource habis
                order["is_scheduled_for_later_try"] = True # Menandai bahwa sudah dicoba hari ini dan akan dicoba lagi nanti

        # Pindah ke hari berikutnya jika tidak ada pesanan lagi yang berhasil dijadwalkan di iterasi saat ini
        # dan masih ada pending_orders. Ini untuk mencegah loop tak terbatas jika ada pesanan yang tidak pernah cocok
        if not scheduled_in_current_day_iteration and pending_orders:
            print(f"\nTidak ada pesanan yang berhasil dijadwalkan pada {current_date_str} di iterasi ini. Pindah ke hari berikutnya.")
        
        current_day_num += 1
        # Lewati Sabtu dan Minggu
        if (current_day_num - 1) % FACTORY_RESOURCES["work_days_per_week"] == 0 and current_day_num > 1:
            current_day_num += 2
        current_date_str = f"Day {current_day_num}"

    print("\n--- Ringkasan Penjadwalan ---")
    if production_log:
        for entry in production_log:
            print(f"Pesanan ID: {entry['order_id']} | Produk: {entry['product_type']} | Mesin: {entry['assigned_machine']} | Tgl: {entry['scheduled_date']}")
            print(f"  Mulai: Menit {entry['start_time_minutes']} | Selesai: Menit {entry['end_time_minutes']} | Durasi: {entry['duration_minutes']:.2f} menit ({entry['duration_minutes']/60:.2f} jam)")
            print(f"  Operator: {entry['operators_assigned']} orang | Daya: {entry['power_consumption_kWh']:.2f} kWh")
        
        # Hitung metrik kinerja dasar
        total_power_all_orders = sum(entry['power_consumption_kWh'] for entry in production_log)
        total_scheduled_orders = len(production_log)
        
        print(f"\nTotal Pesanan Terjadwal: {total_scheduled_orders}/{len(orders_queue)}")
        print(f"Total Konsumsi Daya Kumulatif: {total_power_all_orders:.2f} kWh")

    else:
        print("Tidak ada pesanan yang berhasil dijadwalkan.")


# --- Fungsi untuk Input Pengguna ---

def get_user_orders():
    """
    Meminta input pesanan dari pengguna.
    Mengembalikan daftar kamus pesanan.
    """
    user_orders = []
    order_count = 1
    
    print("\n--- Masukkan Pesanan Produksi ---")
    print("Jenis produk yang didukung: Yane600, Yane672, Yane750, SD680, Kabe325, Aksesoris")
    print("Prioritas: Normal, Mendesak")

    while True:
        print(f"\nPesanan ke-{order_count}:")
        order_id = input(f"  Masukkan ID Pesanan (contoh: P{order_count:03d}, ketik 'selesai' untuk mengakhiri): ").strip()
        if order_id.lower() == 'selesai':
            break

        product_type = ""
        while product_type not in ["Yane600", "Yane672", "Yane750", "SD680", "Kabe325", "Aksesoris"]:
            product_type = input("  Masukkan Jenis Produk (Yane600, Yane672, Yane750, SD680, Kabe325, Aksesoris): ").strip()

        thickness_bmt = input("  Masukkan Ketebalan Material (contoh: 0.5mm): ").strip()
        
        priority = ""
        while priority not in ["Normal", "Mendesak"]:
            priority = input("  Masukkan Prioritas (Normal/Mendesak): ").strip()

        order_data = {
            "order_id": order_id,
            "product_type": product_type,
            "thickness_bmt": thickness_bmt,
            "priority": priority,
            "is_scheduled": False
        }

        if product_type == "Aksesoris":
            try:
                bends_per_accessory = int(input("  Masukkan Jumlah Tekukan per Aksesoris: "))
                num_accessories = int(input("  Masukkan Jumlah Aksesoris yang Dipesan: "))
                order_data["bends_per_accessory"] = bends_per_accessory
                order_data["num_accessories"] = num_accessories
            except ValueError:
                print("Input tidak valid untuk jumlah tekukan/aksesoris. Pesanan ini mungkin bermasalah.")
                continue # Atau tangani lebih baik
        else: # Forming products
            try:
                total_length_m = float(input("  Masukkan Total Panjang Pesanan (dalam meter): "))
                order_data["total_length_m"] = total_length_m
            except ValueError:
                print("Input tidak valid untuk panjang pesanan. Pesanan ini mungkin bermasalah.")
                continue # Atau tangani lebih baik

        user_orders.append(order_data)
        order_count += 1
    
    return user_orders

# --- Eksekusi Program Utama ---
if __name__ == "__main__":
    orders_from_user = get_user_orders()
    if orders_from_user:
        run_production_scheduling_algorithm(orders_from_user)
    else:
        print("Tidak ada pesanan yang dimasukkan. Program berakhir.")
