import chessmodel as cm
import chessview as cv
import chesspresenter as cp

if __name__ == "__main__":
    model = cm.ChessModel()
    view = cv.ChessView()
    presenter = cp.ChessPresenter(model, view)

    presenter.main_loop()