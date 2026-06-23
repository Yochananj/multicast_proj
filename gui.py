import os
import threading

import anyio
import flet as ft

from server import Server


class GUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.server = Server()

        self.page.title = "control"
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.theme_mode = ft.ThemeMode.DARK

        self.death_button = ft.Button(content=ft.Text("death"), width=200, disabled=True)
        self.kill_button = ft.Button(content=ft.Text("kill"), width=200, disabled=True)
        self.stop_screen_sharing_button = ft.Button(content=ft.Text("stop"), width=200, disabled=True)
        self.start_screen_sharing_button = ft.Button(content=ft.Text("go"), width=200, disabled=True)
        self.toggle_freeze_button = ft.Button(content=ft.Text("freeze"), width=200, disabled=True)
        self.password_text_field = ft.TextField(label="Password", width=200)
        self.confirm_password_button = ft.Button(content=ft.Text("confirm"), width=200, disabled=True)
        self.status_text = ft.Text(value="Server: not running\nEnter a password", text_align=ft.TextAlign.CENTER, width=200, size=16, color=ft.Colors.BLUE_200)

        for control in [self.death_button, self.kill_button, self.stop_screen_sharing_button,
                        self.start_screen_sharing_button, self.toggle_freeze_button, self.password_text_field,
                        self.confirm_password_button, self.status_text]:

            self.page.add(control)

        self._attach_buttons_to_handlers()

    def _attach_buttons_to_handlers(self):
        self.start_screen_sharing_button.on_click = lambda _: self._start_screen_share()
        self.stop_screen_sharing_button.on_click = lambda _: self._stop_screen_share()
        self.password_text_field.on_change = lambda _: self._upon_password_text_field_change()
        self.confirm_password_button.on_click = lambda _: self._confirm_password_button_on_click()
        self.kill_button.on_click = self._kill_server_on_click
        self.toggle_freeze_button.on_click = lambda _: self._unfreeze_keyboard_and_mouse() if self.server.should_keep_freezing else self._freeze_keyboard_and_mouse()
        self.death_button.on_click = lambda _: self._death_button_on_click()

    def _start_screen_share(self):
        if not self.server.is_sharing_screen:
            threading.Thread(target=self.server.start_screen_share, args=[], daemon=True).start()
        self.start_screen_sharing_button.disabled, self.stop_screen_sharing_button.disabled = True, False

    def _stop_screen_share(self):
        if self.server.is_sharing_screen:
            self.server.stop_screen_share()
        self.start_screen_sharing_button.disabled, self.stop_screen_sharing_button.disabled = False, True

    def _upon_password_text_field_change(self):
        if self.password_text_field.value.strip() != "":
            self.confirm_password_button.disabled = False
        else:
            self.confirm_password_button.disabled = True

    def _confirm_password_button_on_click(self):
        self.server.create_key(self.password_text_field.value.strip())
        self.start_screen_sharing_button.disabled = False
        self.kill_button.disabled = False
        self.death_button.disabled = False
        self.toggle_freeze_button.disabled = False
        self.confirm_password_button.disabled = True
        self.password_text_field.disabled = True
        self.status_text.value = "Server: running"

    async def _kill_server_on_click(self):
        self.status_text.value, self.status_text.color = "Quitting...", ft.Colors.RED
        self.page.controls.clear()
        self.page.add(self.status_text)

        progress_bar = ft.ProgressBar(color=ft.Colors.RED, width=300, border_radius=ft.BorderRadius.all(10))
        self.page.add(progress_bar)
        self.page.update()

        await anyio.to_thread.run_sync(self.server.kill_server_and_client)
        await self.page.window.destroy()
        os._exit(0)


    def _freeze_keyboard_and_mouse(self):
        threading.Thread(target=self.server.start_freeze, args=[]).start()
        self.toggle_freeze_button.content.value = "unfreeze"

    def _unfreeze_keyboard_and_mouse(self):
        self.server.stop_freeze()
        self.toggle_freeze_button.content.value = "freeze"

    def _death_button_on_click(self):
        self.server.send_shutdown_command()


if __name__ == "__main__":
    ft.run(GUI)