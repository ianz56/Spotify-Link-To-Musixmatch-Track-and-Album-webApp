# Panduan Mengelola Bahasa (Translations)

## 1. Memperbarui Terjemahan yang Sudah Ada

Jika Anda ingin mengubah kata-kata dalam bahasa Indonesia (atau bahasa lain yang sudah ada):

1.  **Buka file terjemahan**:
    Buka file `.po` yang sesuai, misal: `translations/id/LC_MESSAGES/messages.po`.
2.  **Edit Bagian `msgstr`**:
    Cari kata yang ingin diubah.
    ```po
    msgid "Home Page"
    msgstr "Beranda"  <-- Ubah bagian ini
    ```
3.  **Compile**:
    Jalankan script untuk menerapkan perubahan:
    ```bash
    python compile_translations.py
    ```
4.  **Restart Server**:
    Restart Flask server agar perubahan terlihat.

---

## 2. Menambah Bahasa Baru

Misal Anda ingin menambah Bahasa Jepang (kode: `ja`).

1.  **Inisialisasi Bahasa Baru**:
    Jalankan perintah berikut:
    ```bash
    python add_language.py ja
    ```
    *(Ganti `ja` dengan kode bahasa yang diinginkan)*

2.  **Terjemahkan**:
    Buka file yang baru dibuat di `translations/ja/LC_MESSAGES/messages.po` dan isi terjemahannya.

3.  **Compile**:
    ```bash
    python compile_translations.py
    ```

4.  **Update `app.py`**:
    Tambahkan kode bahasa baru ke daftar yang diizinkan di `app.py`:
    ```python
    # Di dalam fungsi get_locale dan route set_language
    if lang in ['en', 'id', 'ja']:  # <-- Tambahkan 'ja'
        return lang
    ```

5.  **Tambahkan Link di Navigasi**:
    Update file HTML (misal `templates/index.html`) untuk menampilkan link bahasa baru:
    ```html
    <a href="{{ url_for('set_language', language='ja') }}">JA</a>
    ```

---

## 3. Menambah Teks Baru di HTML

Jika Anda menambahkan teks baru di file HTML (misal tombol baru):

1.  **Wrap Teks dengan `_()`**:
    ```html
    <button>{{ _('Tombol Baru') }}</button>
    ```
2.  **Ekstrak Pesan**:
    ```bash
    python extract_messages.py
    ```
    *(Ini akan mengupdate `messages.pot`)*
3.  **Update Terjemahan**:
    Jalankan perintah ini untuk mengupdate file `.po` yang ada dengan kata-kata baru (tanpa menghapus terjemahan lama):
    ```bash
    pybabel update -i messages.pot -d translations
    ```
4.  **Terjemahkan & Compile**:
    Edit file `.po` untuk menerjemahkan kata baru tersebut, lalu jalankan `python compile_translations.py`.
