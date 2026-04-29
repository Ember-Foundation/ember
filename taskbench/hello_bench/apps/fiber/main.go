package main

import (
	"log"
	"os"

	"github.com/gofiber/fiber/v2"
)

func main() {
	app := fiber.New(fiber.Config{
		Prefork:               os.Getenv("PREFORK") == "1",
		DisableStartupMessage: false,
	})
	app.Get("/hello", func(c *fiber.Ctx) error {
		c.Set("Content-Type", "text/plain; charset=utf-8")
		return c.SendString("Hello, World!")
	})
	port := os.Getenv("PORT")
	if port == "" {
		port = "9013"
	}
	log.Printf("Fiber on :%s prefork=%v GOMAXPROCS=%s", port, os.Getenv("PREFORK") == "1", os.Getenv("GOMAXPROCS"))
	if err := app.Listen(":" + port); err != nil {
		log.Fatal(err)
	}
}
