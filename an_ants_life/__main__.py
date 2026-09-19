from .main import _parse_args, run


if __name__ == "__main__":
    args = _parse_args()
    run(
        save_path=args.save_file,
        autosave_ticks=args.autosave_ticks,
        max_ticks=args.max_ticks,
        new_game=args.new_game,
    )
