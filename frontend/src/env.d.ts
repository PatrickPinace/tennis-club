/// <reference path="../.astro/types.d.ts" />
/// <reference types="astro/client" />

declare namespace App {
  interface Locals {
    user?: {
      id: number;
      username: string;
      email: string;
      first_name: string;
      last_name: string;
      is_staff: boolean;
    };
  }
}
